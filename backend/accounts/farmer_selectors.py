"""Read-only builders for farmer data shared between branches (FA-02 now; PU-07, AD-03 later)."""

from datetime import timedelta
from typing import Any

from django.db.models import Avg, Count, Prefetch
from django.utils import timezone

from accounts.models import FarmerProfile
from catalog.models import Product
from markets.models import FarmerClosure, FarmerMarket, PickupSlot
from markets.selectors import coordinate, image_url, serialize_closure, serialize_pickup_slot
from markets.services.validation import BOOKING_HORIZON_DAYS
from reviews.models import FarmerReview


def build_farmer_public(
    profile: FarmerProfile, *, request: Any = None, include_inactive_slots: bool = False
) -> dict[str, Any]:
    """FarmerPublic = FarmerSummary & details (Pass 4B §3.2).

    The owner (FA-02) sees inactive slots too; public screens pass include_inactive_slots=False.
    Only active markets are listed. distance_km / is_favorite are filled by the public branch.
    """
    today = timezone.localdate()

    rating = FarmerReview.objects.filter(order__farmer=profile, is_hidden_by_admin=False).aggregate(
        avg=Avg("rating"), count=Count("id")
    )
    in_stock_count = Product.objects.filter(
        farmer=profile,
        is_archived=False,
        is_hidden_by_admin=False,
        is_available=True,
        stock_quantity__gt=0,
    ).count()
    closures = FarmerClosure.objects.filter(
        farmer=profile,
        end_date__gte=today,
        start_date__lte=today + timedelta(days=BOOKING_HORIZON_DAYS),
    ).order_by("start_date", "id")

    slots = PickupSlot.objects.order_by("day_of_week", "start_time", "id")
    if not include_inactive_slots:
        slots = slots.filter(is_active=True)
    farmer_markets = (
        FarmerMarket.objects.filter(farmer=profile, market__is_active=True)
        .select_related("market")
        .prefetch_related(Prefetch("pickup_slots", queryset=slots))
        .order_by("market__name", "id")
    )

    markets, pickup_windows = [], []
    for farmer_market in farmer_markets:
        market = farmer_market.market
        markets.append(
            {"market_id": market.pk, "market_name": market.name, "stall_label": farmer_market.stall_label}
        )
        pickup_windows.append(
            {
                "farmer_market_id": farmer_market.pk,
                "market_id": market.pk,
                "market_name": market.name,
                "stall_label": farmer_market.stall_label,
                "latitude": coordinate(market.latitude),
                "longitude": coordinate(market.longitude),
                "slots": [serialize_pickup_slot(slot) for slot in farmer_market.pickup_slots.all()],
            }
        )

    return {
        "id": profile.pk,
        "stall_name": profile.stall_name,
        "image": image_url(profile.image, request),
        "rating_avg": round(float(rating["avg"]), 1) if rating["avg"] is not None else None,
        "rating_count": rating["count"],
        "markets": markets,
        "operating_days": list(profile.operating_days or []),
        "in_stock_product_count": in_stock_count,
        "upcoming_closures": [serialize_closure(closure) for closure in closures],
        "distance_km": None,
        "is_favorite": None,
        "contact_person": profile.contact_person,
        "phone": profile.phone,
        "address": profile.address,
        "description": profile.description,
        "latitude": coordinate(profile.latitude),
        "longitude": coordinate(profile.longitude),
        "order_cutoff_hours": profile.order_cutoff_hours,
        "pickup_windows": pickup_windows,
    }


def build_farmer_own_profile(profile: FarmerProfile, *, request: Any = None) -> dict[str, Any]:
    """FA-02: FarmerPublic + { email, status, status_reason, location_found }."""
    data = build_farmer_public(profile, request=request, include_inactive_slots=True)
    data.update(
        {
            "email": profile.user.email,
            "status": profile.status,
            "status_reason": profile.status_reason,
            "location_found": profile.latitude is not None and profile.longitude is not None,
        }
    )
    return data
