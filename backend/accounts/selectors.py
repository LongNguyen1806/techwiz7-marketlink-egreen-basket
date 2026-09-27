from datetime import timedelta

from django.db.models import (
    Avg,
    BooleanField,
    Case,
    Count,
    F,
    IntegerField,
    OuterRef,
    Prefetch,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from accounts.models import CustomerProfile, FarmerProfile, FarmerStatus
from catalog.models import Product
from marketlink_core.constants import BOOKING_HORIZON_DAYS
from marketlink_core.geo import distance_km
from marketlink_core.policies.roles import RoleCode
from marketlink_core.ordering import both_directions, resolve_ordering
from marketlink_core.shortcuts import get_or_404
from markets.models import FarmerClosure, FarmerMarket, PickupSlot
from orders.admin_selectors import AT_RISK_STATUSES, at_risk_threshold, at_risk_window_start
from orders.models import OPEN_STATUSES, Order, OrderStatus


# AD-02. user_id breaks ties so paging never shows or skips a row twice.
ADMIN_FARMER_ORDERING = both_directions(
    {
        "stall_name": ("stall_name",),
        "email": ("user__email",),
        "status": ("status",),
        "date_joined": ("user__date_joined",),
        "product_count": ("product_count",),
        "open_order_count": ("open_order_count",),
    },
    tiebreak=("-user_id",),
)
ADMIN_FARMER_ORDERING["newest"] = ("-user__date_joined", "-user_id")


def list_farmers_for_admin(
    *,
    status: str | None = None,
    q: str | None = None,
    market_id: int | None = None,
    ordering: str | None = None,
) -> QuerySet[FarmerProfile]:
    queryset = FarmerProfile.objects.select_related("user").annotate(
        # Archived products are soft-deleted (D-017), so the A-02 column counts the live catalogue.
        product_count=Count("products", filter=Q(products__is_archived=False), distinct=True),
        open_order_count=Count(
            "orders", filter=Q(orders__status__in=OPEN_STATUSES), distinct=True
        ),
    )
    if status in FarmerStatus.values:
        queryset = queryset.filter(status=status)
    if q:
        queryset = queryset.filter(
            Q(stall_name__icontains=q) | Q(user__email__icontains=q) | Q(phone__icontains=q)
        )
    if market_id is not None:
        queryset = queryset.filter(farmer_markets__market_id=market_id)
    return queryset.order_by(
        *resolve_ordering(ordering, allowed=ADMIN_FARMER_ORDERING, default="newest")
    )


def list_pending_farmers(*, limit: int) -> list[FarmerProfile]:
    return list(list_farmers_for_admin(status=FarmerStatus.PENDING)[:limit])


ORDER_WEIGHT = 2
REVIEW_WEIGHT = 1

FARMER_ORDERING = {
    "popular": (
        "-popularity",
        F("rating_avg").desc(nulls_last=True),
        "stall_name",
    ),
    "rating": (F("rating_avg").desc(nulls_last=True), "-rating_count", "stall_name"),
    "in_stock": ("-in_stock_product_count", "stall_name"),
    "name": ("stall_name",),
    "distance": ("distance", "stall_name"),
}


def _in_stock_subquery():
    # A subquery, not a second Count over a joined relation: two multi-valued joins in one
    # annotate would multiply the rows and corrupt both the count and the rating average.
    return Coalesce(
        Subquery(
            Product.objects.filter(
                farmer_id=OuterRef("user_id"),
                is_archived=False,
                is_hidden_by_admin=False,
                is_available=True,
                stock_quantity__gt=0,
            )
            .order_by()
            .values("farmer_id")
            .annotate(total=Count("id"))
            .values("total")[:1],
            output_field=IntegerField(),
        ),
        Value(0),
    )


def public_farmer_base() -> QuerySet[FarmerProfile]:
    # §6.2: a farmer is public only while APPROVED and their account is enabled.
    visible_review = Q(orders__farmer_review__is_hidden_by_admin=False)
    return (
        FarmerProfile.objects.filter(status=FarmerStatus.APPROVED, user__is_active=True)
        .select_related("user")
        .annotate(
            rating_avg=Avg("orders__farmer_review__rating", filter=visible_review),
            rating_count=Count("orders__farmer_review", filter=visible_review, distinct=True),
            completed_order_count=Count(
                "orders",
                filter=Q(orders__status=OrderStatus.COMPLETED),
                distinct=True,
            ),
            in_stock_product_count=_in_stock_subquery(),
        )
        .annotate(
            # Annotated separately: it reads the two counts above, which do not exist yet in
            # the same annotate() call.
            popularity=(
                F("completed_order_count") * ORDER_WEIGHT
                + F("rating_count") * REVIEW_WEIGHT
            )
        )
    )


def public_farmers(
    *, q=None, market_id=None, day=None, category_id=None, coordinates=None, ordering=None
) -> QuerySet[FarmerProfile]:
    queryset = public_farmer_base()
    if q:
        queryset = queryset.filter(Q(stall_name__icontains=q) | Q(address__icontains=q))
    if market_id is not None:
        queryset = queryset.filter(farmer_markets__market_id=market_id)
    if day is not None:
        queryset = queryset.filter(
            operating_days__contains=[day],
            farmer_markets__pickup_slots__day_of_week=day,
            farmer_markets__pickup_slots__is_active=True,
        )
    if category_id is not None:
        queryset = queryset.filter(
            products__category_id=category_id,
            products__is_archived=False,
            products__is_hidden_by_admin=False,
        )
    if coordinates is not None:
        lat, lng = coordinates
        queryset = queryset.annotate(
            distance=distance_km(lat=lat, lng=lng, lat_field="latitude", lng_field="longitude")
        )
    # ordering=distance needs coordinates; without them it falls back to name.
    # No explicit sort means the home page, which wants the busiest stalls first.
    key = ordering if ordering in FARMER_ORDERING else "popular"
    if key == "distance" and coordinates is None:
        key = "name"
    return queryset.distinct().order_by(*FARMER_ORDERING[key])


def public_farmer(*, farmer_id: int) -> FarmerProfile:
    return get_or_404(public_farmer_base(), message="Farmer not found.", pk=farmer_id)


def farmer_market_rows(*, farmer_ids) -> dict[int, list[dict]]:
    rows = (
        FarmerMarket.objects.filter(farmer_id__in=set(farmer_ids), market__is_active=True)
        .select_related("market")
        .order_by("market__name")
    )
    grouped: dict[int, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row.farmer_id, []).append(
            {
                "market_id": row.market_id,
                "market_name": row.market.name,
                "stall_label": row.stall_label,
            }
        )
    return grouped


def farmer_closure_map(*, farmer_ids) -> dict[int, list[FarmerClosure]]:
    horizon_end = timezone.localdate() + timedelta(days=BOOKING_HORIZON_DAYS)
    grouped: dict[int, list[FarmerClosure]] = {}
    rows = FarmerClosure.objects.filter(
        farmer_id__in=set(farmer_ids),
        end_date__gte=timezone.localdate(),
        start_date__lte=horizon_end,
    ).order_by("start_date")
    for closure in rows:
        grouped.setdefault(closure.farmer_id, []).append(closure)
    return grouped


def pickup_windows(*, farmer_id: int) -> list[dict]:
    rows = (
        FarmerMarket.objects.filter(farmer_id=farmer_id, market__is_active=True)
        .select_related("market")
        .prefetch_related(
            Prefetch(
                "pickup_slots",
                queryset=PickupSlot.objects.filter(is_active=True).order_by(
                    "day_of_week", "start_time"
                ),
                to_attr="active_slots",
            )
        )
        .order_by("market__name")
    )
    return [
        {
            "farmer_market_id": row.pk,
            "market_id": row.market_id,
            "market_name": row.market.name,
            "stall_label": row.stall_label,
            "latitude": float(row.market.latitude),
            "longitude": float(row.market.longitude),
            "slots": [
                {
                    "id": slot.pk,
                    "day_of_week": slot.day_of_week,
                    "start_time": slot.start_time.strftime("%H:%M"),
                    "end_time": slot.end_time.strftime("%H:%M"),
                    "is_active": slot.is_active,
                }
                for slot in row.active_slots
            ],
        }
        for row in rows
    ]


# AD-09. The default keeps D-028's rule that customers at risk come first, so the admin sees
# them without scrolling; every other key sorts purely by the column asked for.
ADMIN_CUSTOMER_ORDERING = both_directions(
    {
        "full_name": ("full_name",),
        "email": ("user__email",),
        "date_joined": ("user__date_joined",),
        "total_orders": ("total_orders",),
        "open_orders": ("open_orders",),
        "no_show_count": ("no_show_count",),
        "is_active": ("user__is_active",),
    },
    tiebreak=("-user_id",),
)
ADMIN_CUSTOMER_ORDERING["at_risk"] = ("-at_risk", "-user__date_joined", "-user_id")


def list_customers_for_admin(
    *,
    is_active: bool | None = None,
    q: str | None = None,
    at_risk: bool | None = None,
    ordering: str | None = None,
) -> QuerySet[CustomerProfile]:
    threshold = at_risk_threshold()
    queryset = CustomerProfile.objects.filter(user__role__code=RoleCode.CUSTOMER).select_related(
        "user"
    ).annotate(
        total_orders=Count("user__orders", distinct=True),
        open_orders=Count(
            "user__orders", filter=Q(user__orders__status__in=OPEN_STATUSES), distinct=True
        ),
        no_show_count=Count(
            "user__orders", filter=Q(user__orders__status=OrderStatus.NO_SHOW), distinct=True
        ),
        risk_events=Count(
            "user__orders",
            filter=Q(
                user__orders__status__in=AT_RISK_STATUSES,
                user__orders__created_at__gte=at_risk_window_start(),
            ),
            distinct=True,
        ),
    ).annotate(
        at_risk=Case(
            When(risk_events__gte=threshold, then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        )
    )
    if is_active is not None:
        queryset = queryset.filter(user__is_active=is_active)
    if at_risk is True:
        queryset = queryset.filter(risk_events__gte=threshold)
    elif at_risk is False:
        queryset = queryset.filter(risk_events__lt=threshold)
    if q:
        queryset = queryset.filter(
            Q(full_name__icontains=q) | Q(user__email__icontains=q) | Q(phone__icontains=q)
        )
    return queryset.order_by(
        *resolve_ordering(ordering, allowed=ADMIN_CUSTOMER_ORDERING, default="at_risk")
    )


def customer_for_admin(*, customer_id: int) -> CustomerProfile:
    return get_or_404(
        list_customers_for_admin(), message="Customer not found.", user_id=customer_id
    )


def farmer_for_admin(*, farmer_id: int) -> FarmerProfile:
    return get_or_404(list_farmers_for_admin(), message="Farmer not found.", pk=farmer_id)


def farmer_status_history(*, farmer_id: int) -> list[dict]:
    rows = (
        FarmerProfile.history.filter(user_id=farmer_id)
        .select_related("history_user")
        .order_by("history_date", "history_id")
    )
    trail = []
    previous = None
    for row in rows:
        if previous is not None and row.status == previous:
            continue
        trail.append(
            {
                "from_status": previous,
                "to_status": row.status,
                "reason": row.history_change_reason,
                "changed_by": row.history_user.email if row.history_user else None,
                "changed_at": row.history_date,
            }
        )
        previous = row.status
    return trail


def farmer_order_stats(*, farmer_id: int) -> dict:
    rows = dict(
        Order.objects.filter(farmer_id=farmer_id)
        .values("status")
        .annotate(total=Count("id"))
        .values_list("status", "total")
    )
    return {
        "total": sum(rows.values()),
        "completed": rows.get(OrderStatus.COMPLETED, 0),
        "declined": rows.get(OrderStatus.DECLINED, 0),
        "expired": rows.get(OrderStatus.EXPIRED, 0),
        "no_show": rows.get(OrderStatus.NO_SHOW, 0),
    }

# The Farmer branch's selectors live in accounts/farmer_selectors.py; re-exported so
# `from accounts.selectors import ...` keeps working for both branches.
from accounts.farmer_selectors import (  # noqa: E402,F401
    build_farmer_own_profile,
    build_farmer_public,
)
