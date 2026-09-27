from django.urls import path

from accounts.admin_portal.views_admin_customers import (
    AdminCustomerExportView,
    AdminCustomerActivateView,
    AdminCustomerDeactivateView,
    AdminCustomerDeactivationImpactView,
    AdminCustomerDetailView,
    AdminCustomerListView,
)
from accounts.admin_portal.views_admin_farmers import (
    AdminFarmerExportView,
    AdminFarmerApproveView,
    AdminFarmerDetailView,
    AdminFarmerListView,
    AdminFarmerReinstateView,
    AdminFarmerRejectView,
    AdminFarmerSuspendView,
    AdminFarmerSuspensionImpactView,
)

urlpatterns = [
    path("admin/farmers/", AdminFarmerListView.as_view(), name="admin-farmer-list"),
    path("admin/farmers/<int:id>/", AdminFarmerDetailView.as_view(), name="admin-farmer-detail"),
    path(
        "admin/farmers/<int:id>/suspension-impact/",
        AdminFarmerSuspensionImpactView.as_view(),
        name="admin-farmer-suspension-impact",
    ),
    path(
        "admin/farmers/<int:id>/approve/",
        AdminFarmerApproveView.as_view(),
        name="admin-farmer-approve",
    ),
    path(
        "admin/farmers/<int:id>/reject/",
        AdminFarmerRejectView.as_view(),
        name="admin-farmer-reject",
    ),
    path(
        "admin/farmers/<int:id>/suspend/",
        AdminFarmerSuspendView.as_view(),
        name="admin-farmer-suspend",
    ),
    path(
        "admin/farmers/<int:id>/reinstate/",
        AdminFarmerReinstateView.as_view(),
        name="admin-farmer-reinstate",
    ),
    path(
        "admin/farmers/export/",
        AdminFarmerExportView.as_view(),
        name="admin-farmer-export",
    ),
    path("admin/customers/", AdminCustomerListView.as_view(), name="admin-customer-list"),
    path(
        "admin/customers/export/",
        AdminCustomerExportView.as_view(),
        name="admin-customer-export",
    ),
    path(
        "admin/customers/<int:id>/",
        AdminCustomerDetailView.as_view(),
        name="admin-customer-detail",
    ),
    path(
        "admin/customers/<int:id>/deactivation-impact/",
        AdminCustomerDeactivationImpactView.as_view(),
        name="admin-customer-deactivation-impact",
    ),
    path(
        "admin/customers/<int:id>/deactivate/",
        AdminCustomerDeactivateView.as_view(),
        name="admin-customer-deactivate",
    ),
    path(
        "admin/customers/<int:id>/activate/",
        AdminCustomerActivateView.as_view(),
        name="admin-customer-activate",
    ),
]
