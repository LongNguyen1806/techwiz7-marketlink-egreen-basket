from collections import defaultdict
from collections.abc import Iterable

from django.db.models import Avg, Count, F, Q, QuerySet

from accounts.models import FarmerStatus
from catalog.models import Category, Product
from marketlink_core.shortcuts import get_or_404
from markets.models import PickupSlot
from marketlink_core.ordering import both_directions, resolve_ordering


def list_categories_for_admin() -> QuerySet[Category]:
    return Category.objects.annotate(product_count=Count("products")).order_by(
        "display_order", "name"
    )


def list_active_categories() -> QuerySet[Category]:
    return Category.objects.filter(is_active=True).order_by("display_order", "name")


def count_products_in_category(*, category_id: int) -> int:
    return Category.objects.filter(pk=category_id).aggregate(
        total=Count("products", filter=Q(products__isnull=False))
    )["total"]


# AD-20. rating_avg is an aggregate over reviews, so both directions are written out by hand
# to keep products with no reviews at the bottom either way.
ADMIN_PRODUCT_ORDERING = both_directions(
    {
        "name": ("name",),
        "stall_name": ("farmer__stall_name",),
        "price": ("price",),
        "stock_quantity": ("stock_quantity",),
        "created_at": ("created_at",),
        "is_hidden": ("is_hidden_by_admin",),
    },
    tiebreak=("-id",),
)
ADMIN_PRODUCT_ORDERING["newest"] = ("-created_at", "-id")
ADMIN_PRODUCT_ORDERING["rating"] = (F("rating_avg").asc(nulls_last=True), "-id")
ADMIN_PRODUCT_ORDERING["-rating"] = (F("rating_avg").desc(nulls_last=True), "-id")


def list_products_for_admin(
    *,
    q: str | None = None,
    farmer_id: int | None = None,
    product_id: int | None = None,
    is_hidden: bool | None = None,
    ordering: str | None = None,
) -> QuerySet[Product]:
    queryset = Product.objects.select_related("farmer", "category").annotate(
        rating_avg=Avg(
            "order_items__product_review__rating",
            filter=Q(order_items__product_review__is_hidden_by_admin=False),
        ),
        rating_count=Count(
            "order_items__product_review",
            filter=Q(order_items__product_review__is_hidden_by_admin=False),
            distinct=True,
        ),
    )
    if q:
        queryset = queryset.filter(Q(name__icontains=q) | Q(farmer__stall_name__icontains=q))
    if farmer_id is not None:
        queryset = queryset.filter(farmer_id=farmer_id)
    # One row by id, which is how the follow-up queue hands a flagged product over: the link
    # has to land on that product, not on a page it happens to be somewhere in.
    if product_id is not None:
        queryset = queryset.filter(pk=product_id)
    if is_hidden is not None:
        queryset = queryset.filter(is_hidden_by_admin=is_hidden)
    return queryset.order_by(
        *resolve_ordering(ordering, allowed=ADMIN_PRODUCT_ORDERING, default="newest")
    )


def get_product_for_admin(*, product_id: int) -> Product:
    return list_products_for_admin().get(pk=product_id)


def markets_for_products(*, product_ids: Iterable[int]) -> dict[int, list[dict]]:
    # Farmer operating days come from active pickup slots, not a stored column (§3.2).
    rows = (
        PickupSlot.objects.filter(
            is_active=True,
            farmer_market__farmer__products__id__in=set(product_ids),
        )
        .values(
            "farmer_market__farmer__products__id",
            "farmer_market__market_id",
            "farmer_market__market__name",
            "day_of_week",
        )
        .distinct()
    )
    grouped: dict[int, dict[int, dict]] = defaultdict(dict)
    for row in rows:
        product_id = row["farmer_market__farmer__products__id"]
        market_id = row["farmer_market__market_id"]
        entry = grouped[product_id].setdefault(
            market_id,
            {"market_id": market_id, "market_name": row["farmer_market__market__name"], "days": []},
        )
        entry["days"].append(row["day_of_week"])
    return {
        product_id: [
            {**market, "days": sorted(market["days"])}
            for market in sorted(markets.values(), key=lambda m: m["market_name"])
        ]
        for product_id, markets in grouped.items()
    }


MAX_CART_REFRESH_IDS = 50
PRODUCT_ORDERING = {
    "newest": ("-created_at", "-id"),
    "price_asc": ("price", "id"),
    "price_desc": ("-price", "id"),
    "rating": (F("rating_avg").desc(nulls_last=True), "-rating_count", "id"),
}


def public_product_base() -> QuerySet[Product]:
    # The shared "publicly on sale" rule (§6.2, §3.3). Every public and chatbot query starts
    # here so no branch reinvents the visibility filter.
    return (
        Product.objects.filter(
            is_archived=False,
            is_hidden_by_admin=False,
            farmer__status=FarmerStatus.APPROVED,
            farmer__user__is_active=True,
        )
        .select_related("farmer", "category")
        .annotate(
            rating_avg=Avg(
                "order_items__product_review__rating",
                filter=Q(order_items__product_review__is_hidden_by_admin=False),
            ),
            rating_count=Count(
                "order_items__product_review",
                filter=Q(order_items__product_review__is_hidden_by_admin=False),
                distinct=True,
            ),
        )
    )


def public_products(
    *,
    q=None,
    category_ids=None,
    market_id=None,
    day=None,
    farmer_id=None,
    price_min=None,
    price_max=None,
    in_stock=True,
    ids=None,
    ordering=None,
) -> QuerySet[Product]:
    queryset = public_product_base()
    if ids:
        # Refreshing the cart (C-01) must also return paused and sold-out rows so the
        # frontend can mark them Unavailable, so in_stock does not apply here.
        return queryset.filter(id__in=list(ids)[:MAX_CART_REFRESH_IDS]).order_by("id")
    if in_stock:
        queryset = queryset.filter(is_available=True, stock_quantity__gt=0)
    if q:
        queryset = queryset.filter(Q(name__icontains=q) | Q(farmer__stall_name__icontains=q))
    if category_ids:
        queryset = queryset.filter(category_id__in=category_ids)
    if farmer_id is not None:
        queryset = queryset.filter(farmer_id=farmer_id)
    if market_id is not None:
        queryset = queryset.filter(farmer__farmer_markets__market_id=market_id)
    if day is not None:
        queryset = queryset.filter(
            farmer__farmer_markets__pickup_slots__day_of_week=day,
            farmer__farmer_markets__pickup_slots__is_active=True,
        )
    if price_min is not None:
        queryset = queryset.filter(price__gte=price_min)
    if price_max is not None:
        queryset = queryset.filter(price__lte=price_max)
    order = PRODUCT_ORDERING.get(ordering or "newest", PRODUCT_ORDERING["newest"])
    return queryset.distinct().order_by(*order)


def public_product(*, product_id: int) -> Product:
    return get_or_404(public_product_base(), message="Product not found.", pk=product_id)
