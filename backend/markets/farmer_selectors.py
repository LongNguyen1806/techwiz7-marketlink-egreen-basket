"""Read-only builders for market data shared between branches (FA-04 now; PU-03, PU-04 later)."""

from collections.abc import Iterable
from datetime import timedelta
from typing import Any

from django.db.models import Count, Prefetch, Q
from django.utils import timezone

from accounts.models import FarmerStatus
from markets.models import FarmerClosure, Market, MarketClosure, MarketOperatingDay, PickupSlot
from markets.services.validation import BOOKING_HORIZON_DAYS


def image_url(image: Any, request: Any) -> str | None:
    if not image:
        return None
    return request.build_absolute_uri(image.url) if request is not None else image.url


def coordinate(value: Any) -> float | None:
    return float(value) if value is not None else None


def hhmm(value: Any) -> str:
    return value.strftime("%H:%M")


def serialize_pickup_slot(slot: PickupSlot) -> dict[str, Any]:
    """PickupSlot (Pass 4B §3.2)."""
    return {
        "id": slot.pk,
        "day_of_week": slot.day_of_week,
        "start_time": hhmm(slot.start_time),
        "end_time": hhmm(slot.end_time),
        "is_active": slot.is_active,
    }


def serialize_closure(closure: FarmerClosure | MarketClosure) -> dict[str, Any]:
    """Closure (Pass 4B §3.2), for market_closures and farmer_closures."""
    return {
        "id": closure.pk,
        "start_date": closure.start_date.isoformat(),
        "end_date": closure.end_date.isoformat(),
        "reason": closure.reason,
    }


def build_market_summaries(market_ids: Iterable[int], *, request: Any = None) -> dict[int, dict[str, Any]]:
    """MarketSummary (Pass 4B §3.2) for several markets in a fixed number of queries.

    distance_km and is_favorite depend on the caller (public branch); they are null here.
    """
    today = timezone.localdate()
    upcoming = MarketClosure.objects.filter(
        end_date__gte=today, start_date__lte=today + timedelta(days=BOOKING_HORIZON_DAYS)
    ).order_by("start_date", "id")
    markets = (
        Market.objects.filter(id__in=list(market_ids))
        .annotate(
            approved_farmer_count=Count(
                "farmer_markets",
                filter=Q(farmer_markets__farmer__status=FarmerStatus.APPROVED),
                distinct=True,
            )
        )
        .prefetch_related(
            Prefetch("operating_days", queryset=MarketOperatingDay.objects.order_by("day_of_week")),
            Prefetch("closures", queryset=upcoming, to_attr="upcoming_closures"),
        )
    )
    return {
        market.pk: {
            "id": market.pk,
            "name": market.name,
            "address": market.address,
            "image": image_url(market.image, request),
            "latitude": coordinate(market.latitude),
            "longitude": coordinate(market.longitude),
            "operating_days": [day.day_of_week for day in market.operating_days.all()],
            "open_time": hhmm(market.open_time),
            "close_time": hhmm(market.close_time),
            "upcoming_closures": [serialize_closure(closure) for closure in market.upcoming_closures],
            "farmer_count": market.approved_farmer_count,
            "distance_km": None,
            "is_favorite": None,
        }
        for market in markets
    }
