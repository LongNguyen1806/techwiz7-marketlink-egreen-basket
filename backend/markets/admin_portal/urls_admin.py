from django.urls import path

from markets.admin_portal.views_admin import (
    MarketActivateView,
    MarketClosureDeleteView,
    MarketClosureListCreateView,
    MarketDeactivateView,
    MarketDetailView,
    MarketEditImpactView,
    MarketListCreateView,
)

urlpatterns = [
    path("admin/markets/", MarketListCreateView.as_view(), name="admin-market-list"),
    path("admin/markets/<int:id>/", MarketDetailView.as_view(), name="admin-market-detail"),
    path(
        "admin/markets/<int:id>/impact/",
        MarketEditImpactView.as_view(),
        name="admin-market-impact",
    ),
    path(
        "admin/markets/<int:id>/deactivate/",
        MarketDeactivateView.as_view(),
        name="admin-market-deactivate",
    ),
    path(
        "admin/markets/<int:id>/activate/",
        MarketActivateView.as_view(),
        name="admin-market-activate",
    ),
    path(
        "admin/markets/<int:id>/closures/",
        MarketClosureListCreateView.as_view(),
        name="admin-market-closure-list",
    ),
    path(
        "admin/market-closures/<int:id>/",
        MarketClosureDeleteView.as_view(),
        name="admin-market-closure-detail",
    ),
]
