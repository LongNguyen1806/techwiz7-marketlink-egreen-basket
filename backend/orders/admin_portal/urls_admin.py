from django.urls import path

from orders.admin_portal.views_admin import AdminOrderDetailView, AdminOrderListView

urlpatterns = [
    path("admin/orders/", AdminOrderListView.as_view(), name="admin-order-list"),
    path("admin/orders/<int:id>/", AdminOrderDetailView.as_view(), name="admin-order-detail"),
]
