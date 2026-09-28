from rest_framework.views import APIView

from accounts.customer.serializers_customer import CustomerProfileReadSerializer, CustomerProfileWriteSerializer
from accounts.public_portal.context import farmer_context
from accounts.public_portal.serializers_public import FarmerSummarySerializer
from accounts.services.customer_profile_service import update_customer_profile
from marketlink_core.permissions import IsCustomer
from marketlink_core.responses import api_response
from markets.public_portal.serializers_public import MarketSummarySerializer
from markets.public_portal.views_public import market_context
from notifications.services import serialize_notification
from orders.customer.serializers_customer import OrderSummaryReadSerializer
from orders.services.checkout_service import expire_overdue_before_checkout
from orders.services.customer_dashboard import build_customer_dashboard, sweep_farmers_of


class CustomerProfileView(APIView):
    """CU-02 / CU-03: the signed-in customer's own profile (C-10)."""

    permission_classes = [IsCustomer]

    def get(self, request):
        profile = request.user.customer_profile
        data = CustomerProfileReadSerializer(profile, context={"request": request}).data
        return api_response(message="Profile retrieved", data=data, request=request)

    def patch(self, request):
        serializer = CustomerProfileWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = update_customer_profile(user=request.user, data=serializer.validated_data)
        data = CustomerProfileReadSerializer(profile, context={"request": request}).data
        return api_response(message="Profile updated", data=data, request=request)


class CustomerDashboardView(APIView):
    """CU-01 (C-00): counts, the next pickups, favorite shortcuts and the latest notifications."""

    permission_classes = [IsCustomer]

    def get(self, request):
        expire_overdue_before_checkout(farmer_ids=sweep_farmers_of(request.user))
        blocks = build_customer_dashboard(customer=request.user)
        farmers = list(blocks["favorite_farmers"])
        markets = list(blocks["favorite_markets"])
        data = {
            "counts": blocks["counts"],
            "upcoming": OrderSummaryReadSerializer(blocks["upcoming"], many=True).data,
            "favorite_farmers": FarmerSummarySerializer(
                farmers, many=True, context=farmer_context(request, farmers)
            ).data,
            "favorite_markets": MarketSummarySerializer(
                markets, many=True, context=market_context(request, markets)
            ).data,
            "last_order_id": blocks["last_order_id"],
            "recent_notifications": [serialize_notification(note) for note in blocks["recent_notifications"]],
        }
        return api_response(message="Dashboard retrieved", data=data, request=request)
