from django.urls import path

from markets.farmer.views_farmer import (
    FarmerClosureDetailView,
    FarmerClosureListView,
    FarmerMarketDetailView,
    FarmerMarketListView,
    FarmerPickupSlotDetailView,
    FarmerPickupSlotListView,
)

# Three prefixes (api/farmer/markets/, pickup-slots/, closures/) are included separately
# from marketlink_core/urls.py.
market_urlpatterns = [
    path("", FarmerMarketListView.as_view(), name="farmer-markets-list"),
    path("<int:farmer_market_id>/", FarmerMarketDetailView.as_view(), name="farmer-markets-detail"),
]

pickup_slot_urlpatterns = [
    path("", FarmerPickupSlotListView.as_view(), name="farmer-pickup-slots-list"),
    path("<int:slot_id>/", FarmerPickupSlotDetailView.as_view(), name="farmer-pickup-slots-detail"),
]

closure_urlpatterns = [
    path("", FarmerClosureListView.as_view(), name="farmer-closures-list"),
    path("<int:closure_id>/", FarmerClosureDetailView.as_view(), name="farmer-closures-detail"),
]
