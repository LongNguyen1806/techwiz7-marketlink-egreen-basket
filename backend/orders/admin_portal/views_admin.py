from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from marketlink_core.permissions import IsAdmin
from marketlink_core.responses import api_response
from orders.admin_selectors import (
    ADMIN_ORDER_ORDERING,
    list_orders_for_admin,
    order_for_admin,
)
from orders.customer.serializers_customer import (
    CustomerOrderDetailReadSerializer,
    OrderSummaryReadSerializer,
)
from orders.models import OrderStatus


def _int(raw: str | None) -> int | None:
    try:
        return int(raw) if raw is not None else None
    except ValueError:
        return None


# Read-only on purpose. D-033 says the admin does not act on individual orders; this exists so
# support can answer a question about one, which is a different thing from changing it.
class AdminOrderListView(ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = OrderSummaryReadSerializer

    def get_queryset(self):
        params = self.request.query_params
        return list_orders_for_admin(
            q=params.get("q"),
            status=params.get("status"),
            market_id=_int(params.get("market_id")),
            farmer_id=_int(params.get("farmer_id")),
            customer_id=_int(params.get("customer_id")),
            date_from=params.get("from"),
            date_to=params.get("to"),
            ordering=params.get("ordering"),
        )

    @extend_schema(
        parameters=[
            OpenApiParameter("q", str, description="Order id, customer name, phone, email or stall."),
            OpenApiParameter("status", str, enum=list(OrderStatus.values)),
            OpenApiParameter("market_id", int),
            OpenApiParameter("farmer_id", int),
            OpenApiParameter("customer_id", int),
            OpenApiParameter("from", OpenApiTypes.DATE, description="Pickup date, inclusive."),
            OpenApiParameter("to", OpenApiTypes.DATE, description="Pickup date, inclusive."),
            OpenApiParameter(
                "ordering",
                str,
                enum=sorted(ADMIN_ORDER_ORDERING),
                description="Sort column; prefix with - for descending.",
            ),
        ],
        summary="Find an order",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminOrderDetailView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        responses={200: CustomerOrderDetailReadSerializer, 404: None},
        summary="One order, read only",
    )
    def get(self, request, id: int) -> Response:
        order = order_for_admin(order_id=id)
        data = CustomerOrderDetailReadSerializer(order).data
        return api_response(message="OK", request=request, data=data)
