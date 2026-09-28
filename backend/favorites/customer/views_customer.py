from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.public_portal.context import farmer_context
from accounts.public_portal.serializers_public import FarmerSummarySerializer
from accounts.selectors import public_farmers
from catalog.public_portal.serializers_public import ProductCardSerializer
from catalog.public_portal.views_public import product_context
from catalog.selectors import public_products
from favorites.customer.serializers_customer import (
    FavoriteFarmerWriteSerializer,
    FavoriteMarketWriteSerializer,
    FavoriteProductWriteSerializer,
)
from favorites.selectors import customer_favorite_ids
from favorites.services.favorite_service import add_favorite, remove_favorite
from marketlink_core.pagination import StandardPagination
from marketlink_core.permissions import IsCustomer
from marketlink_core.responses import api_response
from markets.public_portal.serializers_public import MarketSummarySerializer
from markets.public_portal.views_public import market_context
from markets.selectors import public_markets


class FavoriteIdsView(APIView):
    """CU-12."""

    permission_classes = [IsCustomer]

    def get(self, request):
        return api_response(message="Favorites retrieved", data=customer_favorite_ids(request.user), request=request)


class _FavoriteAddView(APIView):
    """POST of CU-14 / CU-16 / CU-17."""

    permission_classes = [IsCustomer]
    kind = ""
    serializer_class = None

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        field, target_id = next(iter(serializer.validated_data.items()))
        add_favorite(customer=request.user, kind=self.kind, target_id=target_id)
        return api_response(message="Added to favorites", data={field: target_id}, status_code=201, request=request)


class _FavoriteListView(_FavoriteAddView):
    """GET of CU-13 / CU-16 / CU-17 (C-08).

    Reuses the public selector, serializer and context of the Guest screens, so a favorite is shown
    exactly as it is in the catalogue, and anything no longer publicly on sale simply drops out (§6.2).
    A sold-out product stays listed: C-08 offers "Notify when back in stock" on it (D-025).
    """

    serializer_class_read = None

    def public_queryset(self, request):
        raise NotImplementedError

    def serializer_context(self, request, page) -> dict:
        raise NotImplementedError

    def get(self, request):
        queryset = self.public_queryset(request).filter(favorited_by__customer=request.user)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        data = self.serializer_class_read(page, many=True, context=self.serializer_context(request, page)).data
        return paginator.get_paginated_response(data)


class _FavoriteRemoveView(APIView):
    """DELETE of CU-15 / CU-16 / CU-17."""

    permission_classes = [IsCustomer]
    kind = ""

    def delete(self, request, target_id: int):
        remove_favorite(customer=request.user, kind=self.kind, target_id=target_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class FavoriteFarmersView(_FavoriteListView):
    kind, serializer_class = "farmer", FavoriteFarmerWriteSerializer
    serializer_class_read = FarmerSummarySerializer

    def public_queryset(self, request):
        return public_farmers()

    def serializer_context(self, request, page) -> dict:
        return farmer_context(request, page)


class FavoriteFarmerView(_FavoriteRemoveView):
    kind = "farmer"


class FavoriteProductsView(_FavoriteListView):
    kind, serializer_class = "product", FavoriteProductWriteSerializer
    serializer_class_read = ProductCardSerializer

    def public_queryset(self, request):
        return public_products(in_stock=False)

    def serializer_context(self, request, page) -> dict:
        return product_context(request, page)


class FavoriteProductView(_FavoriteRemoveView):
    kind = "product"


class FavoriteMarketsView(_FavoriteListView):
    kind, serializer_class = "market", FavoriteMarketWriteSerializer
    serializer_class_read = MarketSummarySerializer

    def public_queryset(self, request):
        return public_markets()

    def serializer_context(self, request, page) -> dict:
        return market_context(request, page)


class FavoriteMarketView(_FavoriteRemoveView):
    kind = "market"
