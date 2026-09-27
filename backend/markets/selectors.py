from datetime import date, timedelta

from django.db.models import Count, Prefetch, Q, QuerySet
from django.utils import timezone

from accounts.models import FarmerStatus
from marketlink_core.constants import BOOKING_HORIZON_DAYS
from marketlink_core.geo import distance_km
from marketlink_core.shortcuts import get_or_404
from markets.models import Market, MarketClosure, MarketOperatingDay
from orders.models import OPEN_STATUSES
from marketlink_core.ordering import both_directions, resolve_ordering

UPCOMING_CLOSURES_ATTR = "upcoming_closure_list"
OPERATING_DAYS_ATTR = "operating_day_list"


def today() -> date:
    return timezone.localdate()


def _market_annotations(queryset: QuerySet[Market]) -> QuerySet[Market]:
    return queryset.annotate(
        farmer_count=Count(
            "farmer_markets",
            filter=Q(farmer_markets__farmer__status=FarmerStatus.APPROVED),
            distinct=True,
        ),
        open_order_count=Count(
            "orders", filter=Q(orders__status__in=OPEN_STATUSES), distinct=True
        ),
    )


def _prefetches() -> list[Prefetch]:
    horizon_end = today() + timedelta(days=BOOKING_HORIZON_DAYS)
    return [
        Prefetch(
            "operating_days",
            queryset=MarketOperatingDay.objects.order_by("day_of_week"),
            to_attr=OPERATING_DAYS_ATTR,
        ),
        Prefetch(
            "closures",
            queryset=MarketClosure.objects.filter(
                end_date__gte=today(), start_date__lte=horizon_end
            ).order_by("start_date"),
            to_attr=UPCOMING_CLOSURES_ATTR,
        ),
    ]


# AD-14.
ADMIN_MARKET_ORDERING = both_directions(
    {
        "name": ("name",),
        "address": ("address",),
        "is_active": ("is_active",),
        "farmer_count": ("farmer_count",),
        "open_order_count": ("open_order_count",),
    },
    tiebreak=("id",),
)


def list_markets_for_admin(
    *, q: str | None = None, is_active: bool | None = None, ordering: str | None = None
) -> QuerySet[Market]:
    queryset = _market_annotations(Market.objects.all()).prefetch_related(*_prefetches())
    if q:
        queryset = queryset.filter(Q(name__icontains=q) | Q(address__icontains=q))
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    return queryset.order_by(
        *resolve_ordering(ordering, allowed=ADMIN_MARKET_ORDERING, default="name")
    )


def get_market_for_admin(*, market_id: int) -> Market:
    return list_markets_for_admin().get(pk=market_id)


def list_closures(*, market_id: int, include_past: bool = False) -> QuerySet[MarketClosure]:
    queryset = MarketClosure.objects.filter(market_id=market_id)
    if not include_past:
        queryset = queryset.filter(end_date__gte=today())
    return queryset.order_by("start_date")



def public_markets(*, q=None, day=None, coordinates=None) -> QuerySet[Market]:
    # §6.2: only active markets are publicly visible.
    queryset = _market_annotations(Market.objects.filter(is_active=True)).prefetch_related(
        *_prefetches()
    )
    if q:
        queryset = queryset.filter(Q(name__icontains=q) | Q(address__icontains=q))
    if day is not None:
        queryset = queryset.filter(operating_days__day_of_week=day)
    if coordinates is not None:
        lat, lng = coordinates
        queryset = queryset.annotate(
            distance=distance_km(lat=lat, lng=lng, lat_field="latitude", lng_field="longitude")
        )
    return queryset.distinct()


def order_public_markets(queryset: QuerySet[Market], *, ordering: str | None, has_coordinates: bool):
    if ordering == "distance" and has_coordinates:
        return queryset.order_by("distance", "name")
    return queryset.order_by("name")


def public_market(*, market_id: int, coordinates=None) -> Market:
    return get_or_404(
        public_markets(coordinates=coordinates), message="Market not found.", pk=market_id
    )


def closure_map(*, market_ids) -> dict[int, list[MarketClosure]]:
    horizon_end = today() + timedelta(days=BOOKING_HORIZON_DAYS)
    grouped: dict[int, list[MarketClosure]] = {}
    rows = MarketClosure.objects.filter(
        market_id__in=set(market_ids), end_date__gte=today(), start_date__lte=horizon_end
    ).order_by("start_date")
    for closure in rows:
        grouped.setdefault(closure.market_id, []).append(closure)
    return grouped

# The Farmer branch's selectors live in markets/farmer_selectors.py; re-exported so
# `from markets.selectors import ...` keeps working for both branches.
from markets.farmer_selectors import (  # noqa: E402,F401
    build_market_summaries,
    coordinate,
    hhmm,
    image_url,
    serialize_closure,
    serialize_pickup_slot,
)
