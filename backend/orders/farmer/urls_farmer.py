from django.urls import path

from orders.farmer.views_farmer import (
    FarmerDashboardView,
    FarmerOrderAcceptView,
    FarmerOrderApproveChangeView,
    FarmerOrderCompleteView,
    FarmerOrderDeclineView,
    FarmerOrderDetailView,
    FarmerOrderGroupedByCustomerView,
    FarmerOrderItemMarkSoldOutView,
    FarmerOrderListView,
    FarmerOrderNoShowView,
    FarmerOrderPickingListView,
    FarmerOrderReadyView,
    FarmerOrderRejectChangeView,
    FarmerOrderTabCountsView,
    FarmerStatsView,
)

urlpatterns = [
    path("", FarmerOrderListView.as_view(), name="farmer-orders-list"),
    path("tab-counts/", FarmerOrderTabCountsView.as_view(), name="farmer-orders-tab-counts"),
    path("picking-list/", FarmerOrderPickingListView.as_view(), name="farmer-orders-picking-list"),
    path(
        "grouped-by-customer/",
        FarmerOrderGroupedByCustomerView.as_view(),
        name="farmer-orders-grouped",
    ),
    path("<int:order_id>/", FarmerOrderDetailView.as_view(), name="farmer-orders-detail"),
    path("<int:order_id>/accept/", FarmerOrderAcceptView.as_view(), name="farmer-orders-accept"),
    path(
        "<int:order_id>/decline/",
        FarmerOrderDeclineView.as_view(),
        name="farmer-orders-decline",
    ),
    path("<int:order_id>/ready/", FarmerOrderReadyView.as_view(), name="farmer-orders-ready"),
    path(
        "<int:order_id>/complete/",
        FarmerOrderCompleteView.as_view(),
        name="farmer-orders-complete",
    ),
    path(
        "<int:order_id>/no-show/",
        FarmerOrderNoShowView.as_view(),
        name="farmer-orders-no-show",
    ),
    path(
        "<int:order_id>/items/<int:product_id>/mark-sold-out/",
        FarmerOrderItemMarkSoldOutView.as_view(),
        name="farmer-orders-item-mark-sold-out",
    ),
    path(
        "<int:order_id>/change-request/approve/",
        FarmerOrderApproveChangeView.as_view(),
        name="farmer-orders-approve-change",
    ),
    path(
        "<int:order_id>/change-request/reject/",
        FarmerOrderRejectChangeView.as_view(),
        name="farmer-orders-reject-change",
    ),
]

dashboard_urlpatterns = [
    path("", FarmerDashboardView.as_view(), name="farmer-dashboard"),
    path("stats/", FarmerStatsView.as_view(), name="farmer-stats"),
]
