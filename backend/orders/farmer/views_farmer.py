from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Count, Prefetch, Q, QuerySet, Sum
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import FarmerProfile
from marketlink_core.exceptions import (
    BusinessValidationError,
    ErrorCode,
    ResourceNotFoundError,
)
from marketlink_core.http import parse_if_match
from marketlink_core.pagination import StandardPagination
from marketlink_core.permissions import IsFarmer
from marketlink_core.responses import api_response
from orders.farmer.serializers_farmer import (
    DeclineOrderSerializer,
    FarmerOrderDetailSerializer,
    FarmerOrderSummarySerializer,
    PrepListItemSerializer,
    RejectChangeRequestSerializer,
)
from orders.models import ActorRole, Order, OrderItem, OrderStatus, OrderStatusHistory
from orders.services.dashboard import build_farmer_dashboard, build_farmer_stats, resolve_date_range
from orders.services.expiry import expire_overdue_orders
from orders.services.farmer_change_request import approve_change_request, reject_change_request
from orders.services.farmer_order_items import mark_order_item_sold_out
from orders.services.fsm import transition_order

_S = OrderStatus
HISTORY_STATUSES = [_S.COMPLETED, _S.CANCELLED, _S.DECLINED, _S.NO_SHOW, _S.EXPIRED]
IN_PROGRESS_STATUSES = [_S.ACCEPTED, _S.READY_FOR_PICKUP]

TAB_RULES: dict[str, tuple[list[str], tuple[str, ...]]] = {
    "placed": ([_S.PLACED], ("created_at", "id")),
    "accepted": ([_S.ACCEPTED], ("pickup_start_at", "id")),
    "ready": ([_S.READY_FOR_PICKUP], ("pickup_start_at", "id")),
    "history": (HISTORY_STATUSES, ("-created_at", "-id")),
}
PLACED_ORDERINGS = {"created_at": ("created_at", "id"), "pickup_start_at": ("pickup_start_at", "id")}
BOOLEAN_VALUES = ("true", "false")


def _parse_int(params: Any, name: str, errors: dict[str, list[str]]) -> int | None:
    raw = params.get(name)
    if raw in (None, ""):
        return None
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value < 1:
        errors[name] = ["Must be a positive integer."]
        return None
    return value


def _parse_date(params: Any, name: str, errors: dict[str, list[str]], *, required: bool = False) -> date | None:
    raw = params.get(name)
    if raw in (None, ""):
        if required:
            errors[name] = ["This parameter is required (YYYY-MM-DD)."]
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        errors[name] = ["Use the YYYY-MM-DD format."]
        return None


def _parse_bool(params: Any, name: str, errors: dict[str, list[str]]) -> bool:
    raw = params.get(name)
    if raw in (None, ""):
        return False
    if raw.lower() not in BOOLEAN_VALUES:
        errors[name] = ["Use true or false."]
        return False
    return raw.lower() == "true"


def _raise_if_errors(errors: dict[str, list[str]]) -> None:
    if errors:
        raise BusinessValidationError(
            "Invalid query parameters.", code=ErrorCode.VALIDATION_ERROR, errors=errors
        )


def _summary_queryset() -> QuerySet:
    return Order.objects.select_related("customer__customer_profile", "farmer", "market").prefetch_related(
        "items__product"
    )


def _detail_queryset() -> QuerySet:
    history = OrderStatusHistory.objects.select_related("actor__customer_profile", "actor__farmer_profile")
    return _summary_queryset().prefetch_related(Prefetch("status_history", queryset=history))


def _detail_response(request: Request, order_id: int, message: str) -> Response:
    order = _detail_queryset().get(id=order_id)
    data = FarmerOrderDetailSerializer(order, context={"request": request}).data
    return api_response(message=message, data=data, request=request)


class FarmerBaseOrderView(APIView):
    permission_classes = [IsFarmer]


class FarmerOrderListView(FarmerBaseOrderView):
    """FA-19: orders of the current farmer, one tab at a time."""

    pagination_class = StandardPagination

    def get(self, request: Request) -> Response:
        params = request.query_params
        errors: dict[str, list[str]] = {}

        tab = params.get("tab", "placed")
        if tab not in TAB_RULES:
            errors["tab"] = [f"Use one of: {', '.join(TAB_RULES)}."]
        status_filter = params.get("status") or None
        if status_filter and status_filter not in _S.values:
            errors["status"] = ["Unknown order status."]
        ordering = params.get("ordering") or None
        if ordering and (tab != "placed" or ordering not in PLACED_ORDERINGS):
            errors["ordering"] = [f"Only the placed tab accepts: {', '.join(PLACED_ORDERINGS)}."]
        market_id = _parse_int(params, "market_id", errors)
        pickup_from = _parse_date(params, "pickup_from", errors)
        pickup_to = _parse_date(params, "pickup_to", errors)
        if pickup_from and pickup_to and pickup_from > pickup_to:
            errors["pickup_to"] = ["Must be on or after pickup_from."]
        overdue = _parse_bool(params, "overdue", errors)
        change_requested = _parse_bool(params, "change_requested", errors)
        _raise_if_errors(errors)

        farmer_id = request.user.pk
        expire_overdue_orders(farmer_id=farmer_id)

        statuses, order_by = TAB_RULES[tab]
        if ordering:
            order_by = PLACED_ORDERINGS[ordering]
        qs = Order.objects.filter(farmer_id=farmer_id, status__in=statuses)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if market_id is not None:
            qs = qs.filter(market_id=market_id)
        if pickup_from:
            qs = qs.filter(pickup_date__gte=pickup_from)
        if pickup_to:
            qs = qs.filter(pickup_date__lte=pickup_to)
        q = params.get("q", "").strip()
        if q:
            by_name = Q(customer__customer_profile__full_name__icontains=q)
            qs = qs.filter(Q(id=int(q)) | by_name) if q.isdigit() else qs.filter(by_name)
        if overdue:
            qs = qs.filter(status__in=IN_PROGRESS_STATUSES, pickup_end_at__lt=timezone.now())
        if change_requested:
            qs = qs.filter(pending_change__isnull=False)

        qs = (
            qs.select_related("customer__customer_profile", "farmer", "market")
            .prefetch_related("items__product")
            .order_by(*order_by)
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = FarmerOrderSummarySerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


class FarmerOrderDetailView(FarmerBaseOrderView):
    """FA-22."""

    def get(self, request: Request, order_id: int) -> Response:
        order = _detail_queryset().filter(id=order_id, farmer_id=request.user.pk).first()
        if not order:
            raise ResourceNotFoundError("Order not found.", code=ErrorCode.NOT_FOUND)
        data = FarmerOrderDetailSerializer(order, context={"request": request}).data
        return api_response(message="OK", data=data, request=request)


class FarmerOrderAcceptView(FarmerBaseOrderView):
    def post(self, request: Request, order_id: int) -> Response:
        version = parse_if_match(request)
        order = transition_order(
            order_id=order_id,
            to_status=OrderStatus.ACCEPTED,
            actor=request.user,
            actor_role=ActorRole.FARMER,
            expected_version=version,
        )
        return _detail_response(request, order.id, "Order accepted successfully.")


class FarmerOrderDeclineView(FarmerBaseOrderView):
    def post(self, request: Request, order_id: int) -> Response:
        version = parse_if_match(request)
        serializer = DeclineOrderSerializer(data=request.data)
        if not serializer.is_valid():
            raise BusinessValidationError(
                "Invalid decline data.",
                code=ErrorCode.VALIDATION_ERROR,
                errors=serializer.errors,
            )

        data = serializer.validated_data
        mark_all_sold_out = False
        sold_out_product_ids: list[int] | None = None
        if "mark_sold_out" in data:
            mark_all_sold_out = data["mark_sold_out"]
            sold_out_product_ids = None if mark_all_sold_out else []
        elif "mark_sold_out_product_ids" in data:
            sold_out_product_ids = data["mark_sold_out_product_ids"]

        order = transition_order(
            order_id=order_id,
            to_status=OrderStatus.DECLINED,
            actor=request.user,
            actor_role=ActorRole.FARMER,
            expected_version=version,
            reason=data["reason"],
            sold_out_product_ids=sold_out_product_ids,
            mark_all_sold_out=mark_all_sold_out,
        )
        return _detail_response(request, order.id, "Order declined successfully.")


class FarmerOrderItemMarkSoldOutView(FarmerBaseOrderView):
    def post(self, request: Request, order_id: int, product_id: int) -> Response:
        """FA-36: remove a sold-out item from a PLACED order and set its stock to 0."""
        version = parse_if_match(request)
        order = mark_order_item_sold_out(
            order_id=order_id,
            product_id=product_id,
            actor=request.user,
            expected_version=version,
        )
        return _detail_response(request, order.id, "Item marked as sold out.")


class FarmerOrderReadyView(FarmerBaseOrderView):
    def post(self, request: Request, order_id: int) -> Response:
        version = parse_if_match(request)
        order = transition_order(
            order_id=order_id,
            to_status=OrderStatus.READY_FOR_PICKUP,
            actor=request.user,
            actor_role=ActorRole.FARMER,
            expected_version=version,
        )
        return _detail_response(request, order.id, "Order is ready for pickup.")


class FarmerOrderCompleteView(FarmerBaseOrderView):
    def post(self, request: Request, order_id: int) -> Response:
        version = parse_if_match(request)
        order = transition_order(
            order_id=order_id,
            to_status=OrderStatus.COMPLETED,
            actor=request.user,
            actor_role=ActorRole.FARMER,
            expected_version=version,
        )
        return _detail_response(request, order.id, "Order completed successfully.")


class FarmerOrderNoShowView(FarmerBaseOrderView):
    def post(self, request: Request, order_id: int) -> Response:
        version = parse_if_match(request)
        order = transition_order(
            order_id=order_id,
            to_status=OrderStatus.NO_SHOW,
            actor=request.user,
            actor_role=ActorRole.FARMER,
            expected_version=version,
        )
        return _detail_response(request, order.id, "Order marked as no-show.")


class FarmerOrderApproveChangeView(FarmerBaseOrderView):
    def post(self, request: Request, order_id: int) -> Response:
        version = parse_if_match(request)
        order = approve_change_request(
            order_id=order_id,
            farmer_id=request.user.pk,
            expected_version=version,
            actor=request.user,
        )
        return _detail_response(request, order.id, "Change request approved.")


class FarmerOrderRejectChangeView(FarmerBaseOrderView):
    def post(self, request: Request, order_id: int) -> Response:
        version = parse_if_match(request)
        serializer = RejectChangeRequestSerializer(data=request.data)
        if not serializer.is_valid():
            raise BusinessValidationError(
                "Invalid rejection data.",
                code=ErrorCode.VALIDATION_ERROR,
                errors=serializer.errors,
            )

        reason = serializer.validated_data.get("reason")
        order = reject_change_request(
            order_id=order_id,
            farmer_id=request.user.pk,
            expected_version=version,
            actor=request.user,
            reason=reason,
        )
        return _detail_response(request, order.id, "Change request rejected.")


class FarmerOrderGroupedByCustomerView(FarmerBaseOrderView):
    """FA-37: accepted / ready orders of one pickup date grouped by customer (D-005 v1.5)."""

    def get(self, request: Request) -> Response:
        params = request.query_params
        errors: dict[str, list[str]] = {}
        pickup_date = _parse_date(params, "pickup_date", errors, required=True)
        market_id = _parse_int(params, "market_id", errors)
        _raise_if_errors(errors)

        farmer_id = request.user.pk
        expire_overdue_orders(farmer_id=farmer_id)

        orders_qs = (
            Order.objects.filter(
                farmer_id=farmer_id, status__in=IN_PROGRESS_STATUSES, pickup_date=pickup_date
            )
            .select_related("customer__customer_profile")
            .prefetch_related("items")
            .order_by("customer_id", "pickup_start_at", "id")
        )
        if market_id is not None:
            orders_qs = orders_qs.filter(market_id=market_id)

        grouped: dict[int, dict[str, Any]] = {}
        for order in orders_qs:
            profile = getattr(order.customer, "customer_profile", None)
            group = grouped.setdefault(
                order.customer_id,
                {
                    "customer_id": order.customer_id,
                    "customer_name": profile.full_name if profile else order.customer.email,
                    "customer_phone": profile.phone if profile else "",
                    "pickup_date": pickup_date.isoformat(),
                    "order_count": 0,
                    "total_amount": Decimal("0.00"),
                    "orders": [],
                },
            )
            group["order_count"] += 1
            group["total_amount"] += order.total_amount
            group["orders"].append(
                {
                    "order_id": order.id,
                    "status": order.status,
                    "stall_label": order.stall_label,
                    "total_amount": str(order.total_amount),
                    "item_count": len(order.items.all()),
                }
            )
        data = [{**group, "total_amount": str(group["total_amount"])} for group in grouped.values()]
        return api_response(message="OK", data=data, request=request)


class FarmerOrderTabCountsView(FarmerBaseOrderView):
    """FA-20."""

    def get(self, request: Request) -> Response:
        errors: dict[str, list[str]] = {}
        market_id = _parse_int(request.query_params, "market_id", errors)
        _raise_if_errors(errors)

        farmer_id = request.user.pk
        expire_overdue_orders(farmer_id=farmer_id)

        base_qs = Order.objects.filter(farmer_id=farmer_id)
        if market_id is not None:
            base_qs = base_qs.filter(market_id=market_id)
        data = {
            "placed": base_qs.filter(status=_S.PLACED).count(),
            "accepted": base_qs.filter(status=_S.ACCEPTED).count(),
            "ready": base_qs.filter(status=_S.READY_FOR_PICKUP).count(),
            "overdue": base_qs.filter(
                status__in=IN_PROGRESS_STATUSES, pickup_end_at__lt=timezone.now()
            ).count(),
            "change_requests": base_qs.filter(status=_S.ACCEPTED, pending_change__isnull=False).count(),
            "by_date": _open_counts_by_date(base_qs),
        }
        return api_response(message="OK", data=data, request=request)


_TAB_BY_OPEN_STATUS = {_S.PLACED: "placed", _S.ACCEPTED: "accepted", _S.READY_FOR_PICKUP: "ready"}


def _open_counts_by_date(base_qs: QuerySet[Order]) -> dict[str, dict[str, int]]:
    """Open orders per pickup date from today on, split by tab, for F-02's pickup-day filter."""
    rows = (
        base_qs.filter(status__in=list(_TAB_BY_OPEN_STATUS), pickup_date__gte=timezone.localdate())
        .values("pickup_date", "status")
        .annotate(total=Count("id"))
        .order_by("pickup_date")
    )
    by_date: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = by_date.setdefault(row["pickup_date"].isoformat(), {"placed": 0, "accepted": 0, "ready": 0})
        bucket[_TAB_BY_OPEN_STATUS[row["status"]]] = row["total"]
    return by_date


class FarmerOrderPickingListView(FarmerBaseOrderView):
    """FA-21: total quantity per product for one pickup date (U-03)."""

    def get(self, request: Request) -> Response:
        params = request.query_params
        errors: dict[str, list[str]] = {}
        pickup_date = _parse_date(params, "pickup_date", errors, required=True)
        market_id = _parse_int(params, "market_id", errors)
        _raise_if_errors(errors)

        farmer_id = request.user.pk
        expire_overdue_orders(farmer_id=farmer_id)

        items_qs = OrderItem.objects.filter(
            order__farmer_id=farmer_id,
            order__pickup_date=pickup_date,
            order__status__in=IN_PROGRESS_STATUSES,
        )
        if market_id is not None:
            items_qs = items_qs.filter(order__market_id=market_id)

        aggregated = (
            items_qs.values("product_id", "product_name", "unit")
            .annotate(total_quantity=Sum("quantity"), order_count=Count("order_id", distinct=True))
            .order_by("product_name")
        )
        return api_response(
            message="OK",
            data={
                "pickup_date": pickup_date.isoformat(),
                "market_id": market_id,
                "rows": PrepListItemSerializer(aggregated, many=True).data,
            },
            request=request,
        )


class FarmerDashboardView(FarmerBaseOrderView):
    def get(self, request: Request) -> Response:
        """FA-01 (F-01): KPIs, revenue by day, best sellers, overdue warning, upcoming orders."""
        date_range = resolve_date_range(request.query_params.get("from"), request.query_params.get("to"))
        farmer = FarmerProfile.objects.filter(pk=request.user.pk).first()
        if farmer is None:
            raise ResourceNotFoundError("Farmer profile not found.", code=ErrorCode.NOT_FOUND)
        expire_overdue_orders(farmer_id=farmer.pk)

        data = build_farmer_dashboard(farmer=farmer, date_range=date_range)
        data["upcoming"] = FarmerOrderSummarySerializer(
            data["upcoming"], many=True, context={"request": request}
        ).data
        return api_response(message="OK", data=data, request=request)


class FarmerStatsView(FarmerBaseOrderView):
    def get(self, request: Request) -> Response:
        """FA-01b: the Stats page (sales, best sellers, markets, statuses) over a chosen range."""
        date_range = resolve_date_range(request.query_params.get("from"), request.query_params.get("to"))
        farmer = FarmerProfile.objects.filter(pk=request.user.pk).first()
        if farmer is None:
            raise ResourceNotFoundError("Farmer profile not found.", code=ErrorCode.NOT_FOUND)
        expire_overdue_orders(farmer_id=farmer.pk)

        return api_response(message="OK", data=build_farmer_stats(farmer=farmer, date_range=date_range), request=request)
