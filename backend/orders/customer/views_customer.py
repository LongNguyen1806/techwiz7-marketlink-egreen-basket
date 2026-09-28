from django.db import transaction
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from marketlink_core.exceptions import ResourceNotFoundError
from marketlink_core.http import parse_if_match, require_idempotency_key
from marketlink_core.pagination import StandardPagination
from marketlink_core.permissions import IsCustomer
from marketlink_core.responses import api_response
from marketlink_core.services.db_retry import run_with_deadlock_retry
from orders.customer.serializers_customer import (
    CancelOrderWriteSerializer,
    CheckoutWriteSerializer,
    CustomerOrderDetailReadSerializer,
    CustomerOrderListQuerySerializer,
    CustomerOrderModifySerializer,
    OrderSummaryReadSerializer,
)
from catalog.public_portal.serializers_public import ProductCardSerializer
from catalog.public_portal.views_public import product_context
from orders.selectors import (
    customer_order_detail,
    customer_orders_queryset,
    order_summary_queryset,
    reorder_items,
)
from orders.services.checkout_service import expire_overdue_before_checkout, place_orders
from orders.services.customer_order_service import cancel_customer_order, modify_customer_order
from orders.services.idempotency_service import run_idempotent


def _checkout_with_summaries(*, customer, groups) -> list:
    # The response is built inside the same transaction: if it fails the orders roll back too, so the
    # idempotency key can safely be released and a retry cannot create the orders a second time.
    with transaction.atomic():
        orders = place_orders(customer=customer, groups=groups)
        return OrderSummaryReadSerializer(order_summary_queryset([order.pk for order in orders]), many=True).data


def _place_orders(request) -> tuple[int, dict]:
    serializer = CheckoutWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    groups = serializer.validated_data["groups"]
    # v1.7: the lazy sweep commits on its own, before the checkout transaction starts.
    expire_overdue_before_checkout(farmer_ids=[group["farmer_id"] for group in groups])
    summaries = run_with_deadlock_retry(_checkout_with_summaries, customer=request.user, groups=groups)
    return 201, api_response(
        message=f"Placed {len(summaries)} order(s) successfully", data={"orders": summaries}, status_code=201, request=request
    ).data


class CustomerOrdersView(APIView):
    permission_classes = [IsCustomer]
    throttle_scope = "orders"

    def get_throttles(self):
        # Pass 4B §1.4 / D-005 guard 3: every POST to this endpoint counts toward "orders" (10/hour);
        # modify and cancel live on other endpoints and are not limited by it.
        return [ScopedRateThrottle()] if self.request.method == "POST" else super().get_throttles()

    def post(self, request):
        key = require_idempotency_key(request)
        result = run_idempotent(user_id=request.user.pk, key=key, payload=request.data, action=lambda: _place_orders(request))
        headers = {"Idempotent-Replayed": "true"} if result.replayed else None
        return Response(result.body, status=result.status, headers=headers)

    def get(self, request):
        """CU-05: own orders, paginated (C-04)."""
        query = CustomerOrderListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(customer_orders_queryset(request.user, **query.validated_data), request, view=self)
        return paginator.get_paginated_response(OrderSummaryReadSerializer(page, many=True).data)


def _own_order_detail(request, order_id: int) -> dict:
    order = customer_order_detail(request.user, order_id)
    if order is None:
        raise ResourceNotFoundError()
    return CustomerOrderDetailReadSerializer(order).data


class CustomerOrderDetailView(APIView):
    """CU-06 (C-05) and CU-07 (C-06)."""

    permission_classes = [IsCustomer]

    def get(self, request, order_id: int):
        return api_response(message="Order retrieved", data=_own_order_detail(request, order_id), request=request)

    def patch(self, request, order_id: int):
        expected_version = parse_if_match(request)
        serializer = CustomerOrderModifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = run_with_deadlock_retry(
            modify_customer_order, customer=request.user, order_id=order_id, expected_version=expected_version,
            data=serializer.validated_data,
        )
        message = "Change request sent to the farmer" if order.pending_change else "Order updated"
        return api_response(message=message, data=_own_order_detail(request, order_id), request=request)


class CustomerOrderCancelView(APIView):
    """CU-08: If-Match required; T5 / T6 through the shared FSM."""

    permission_classes = [IsCustomer]

    def post(self, request, order_id: int):
        expected_version = parse_if_match(request)
        serializer = CancelOrderWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run_with_deadlock_retry(
            cancel_customer_order, customer=request.user, order_id=order_id, expected_version=expected_version,
            reason=serializer.validated_data.get("reason"),
        )
        return api_response(message="Order cancelled", data=_own_order_detail(request, order_id), request=request)


class CustomerOrderReorderPreviewView(APIView):
    """CU-09: what of this order can go back in the cart, at today's prices (C-04, C-05)."""

    permission_classes = [IsCustomer]

    def get(self, request, order_id: int):
        order = customer_order_detail(request.user, order_id)
        if order is None:
            raise ResourceNotFoundError()
        kept, skipped = reorder_items(order)
        products = [product for product, _ in kept]
        cards = ProductCardSerializer(products, many=True, context=product_context(request, products)).data
        items = [{"product": card, "quantity": quantity} for card, (_, quantity) in zip(cards, kept)]
        return api_response(message="Reorder preview", data={"items": items, "skipped": skipped}, request=request)
