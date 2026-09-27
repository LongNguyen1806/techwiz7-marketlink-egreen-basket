from typing import Any

from django.db.models import Count, Prefetch
from django.utils import timezone
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import FarmerProfile
from marketlink_core.exceptions import BusinessValidationError, ErrorCode, ResourceNotFoundError
from marketlink_core.permissions import IsFarmer
from marketlink_core.responses import api_response
from markets.farmer.serializers_farmer import (
    CreateClosureFarmerSerializer,
    CreatePickupSlotFarmerSerializer,
    JoinMarketFarmerSerializer,
    UpdatePickupSlotFarmerSerializer,
    UpdateStallLabelFarmerSerializer,
)
from markets.models import FarmerClosure, FarmerMarket, PickupSlot
from markets.selectors import build_market_summaries, serialize_closure, serialize_pickup_slot
from markets.services import farmer_schedule
from orders.models import OPEN_STATUSES, Order

TRUE_VALUES, FALSE_VALUES = ("true", "1"), ("false", "0", "")


class FarmerScheduleBaseView(APIView):
    """F3 (F-07). Every farmer status may manage its own markets, slots and time off (v1.8)."""

    permission_classes = [IsFarmer]

    def _get_profile(self, request: Request) -> FarmerProfile:
        profile = getattr(request.user, "farmer_profile", None)
        if profile is None:
            raise ResourceNotFoundError("Farmer profile not found.", code=ErrorCode.NOT_FOUND)
        return profile


def _farmer_market_items(
    profile: FarmerProfile, *, request: Request, farmer_market_ids: list[int] | None = None
) -> list[dict[str, Any]]:
    """FA-04 item: { id, market: MarketSummary, stall_label, slots, open_order_count } (+ is_market_active)."""
    farmer_markets = (
        FarmerMarket.objects.filter(farmer=profile)
        .select_related("market")
        .prefetch_related(
            Prefetch("pickup_slots", queryset=PickupSlot.objects.order_by("day_of_week", "start_time", "id"))
        )
        .order_by("market__name", "id")
    )
    if farmer_market_ids is not None:
        farmer_markets = farmer_markets.filter(pk__in=farmer_market_ids)
    farmer_markets = list(farmer_markets)

    market_ids = [fm.market_id for fm in farmer_markets]
    summaries = build_market_summaries(market_ids, request=request)
    open_counts = dict(
        Order.objects.filter(farmer=profile, market_id__in=market_ids, status__in=OPEN_STATUSES)
        .values("market_id")
        .annotate(total=Count("id"))
        .values_list("market_id", "total")
    )
    return [
        {
            "id": fm.pk,
            "market": summaries[fm.market_id],
            # Not in MarketSummary: lets F-07 show markets closed by an admin (AD-17).
            "is_market_active": fm.market.is_active,
            "stall_label": fm.stall_label,
            "slots": [serialize_pickup_slot(slot) for slot in fm.pickup_slots.all()],
            "open_order_count": open_counts.get(fm.market_id, 0),
        }
        for fm in farmer_markets
    ]


class FarmerMarketListView(FarmerScheduleBaseView):
    def get(self, request: Request) -> Response:
        """FA-04."""
        profile = self._get_profile(request)
        return api_response(message="OK", data=_farmer_market_items(profile, request=request), request=request)

    def post(self, request: Request) -> Response:
        """FA-05."""
        profile = self._get_profile(request)
        serializer = JoinMarketFarmerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        farmer_market = farmer_schedule.join_market(farmer_id=profile.pk, **serializer.validated_data)
        item = _farmer_market_items(profile, request=request, farmer_market_ids=[farmer_market.pk])[0]
        return api_response(
            message="Market added.", data=item, status_code=status.HTTP_201_CREATED, request=request
        )


class FarmerMarketDetailView(FarmerScheduleBaseView):
    def patch(self, request: Request, farmer_market_id: int) -> Response:
        """FA-06."""
        profile = self._get_profile(request)
        serializer = UpdateStallLabelFarmerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        farmer_schedule.update_stall_label(
            farmer_id=profile.pk, farmer_market_id=farmer_market_id, **serializer.validated_data
        )
        item = _farmer_market_items(profile, request=request, farmer_market_ids=[farmer_market_id])[0]
        return api_response(message="Stall location updated.", data=item, request=request)

    def delete(self, request: Request, farmer_market_id: int) -> Response:
        """FA-07."""
        profile = self._get_profile(request)
        farmer_schedule.leave_market(farmer_id=profile.pk, farmer_market_id=farmer_market_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class FarmerPickupSlotListView(FarmerScheduleBaseView):
    def post(self, request: Request) -> Response:
        """FA-08."""
        profile = self._get_profile(request)
        serializer = CreatePickupSlotFarmerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        slot = farmer_schedule.create_pickup_slot(farmer_id=profile.pk, **serializer.validated_data)
        return api_response(
            message="Pickup slot created.",
            data=serialize_pickup_slot(slot),
            status_code=status.HTTP_201_CREATED,
            request=request,
        )


class FarmerPickupSlotDetailView(FarmerScheduleBaseView):
    def patch(self, request: Request, slot_id: int) -> Response:
        """FA-09."""
        profile = self._get_profile(request)
        serializer = UpdatePickupSlotFarmerSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        slot = farmer_schedule.update_pickup_slot(
            farmer_id=profile.pk, slot_id=slot_id, changes=serializer.validated_data
        )
        return api_response(message="Pickup slot updated.", data=serialize_pickup_slot(slot), request=request)

    def delete(self, request: Request, slot_id: int) -> Response:
        """FA-10."""
        profile = self._get_profile(request)
        farmer_schedule.delete_pickup_slot(farmer_id=profile.pk, slot_id=slot_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class FarmerClosureListView(FarmerScheduleBaseView):
    def get(self, request: Request) -> Response:
        """FA-31: upcoming and current time off; include_past=true adds finished ones."""
        profile = self._get_profile(request)
        raw = (request.query_params.get("include_past") or "").strip().lower()
        if raw not in TRUE_VALUES + FALSE_VALUES:
            raise BusinessValidationError(
                "Invalid query parameters.", errors={"include_past": ["Use true or false."]}
            )
        closures = FarmerClosure.objects.filter(farmer=profile)
        if raw not in TRUE_VALUES:
            closures = closures.filter(end_date__gte=timezone.localdate())
        data = [serialize_closure(closure) for closure in closures.order_by("start_date", "id")]
        return api_response(message="OK", data=data, request=request)

    def post(self, request: Request) -> Response:
        """FA-32."""
        profile = self._get_profile(request)
        serializer = CreateClosureFarmerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        closure = farmer_schedule.create_farmer_closure(farmer_id=profile.pk, **serializer.validated_data)
        return api_response(
            message="Time off added.",
            data=serialize_closure(closure),
            status_code=status.HTTP_201_CREATED,
            request=request,
        )


class FarmerClosureDetailView(FarmerScheduleBaseView):
    def delete(self, request: Request, closure_id: int) -> Response:
        """FA-33."""
        profile = self._get_profile(request)
        farmer_schedule.delete_farmer_closure(farmer_id=profile.pk, closure_id=closure_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
