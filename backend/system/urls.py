from django.urls import path

from system.views import (
    AdminChangeLogView,
    AdminFlagListView,
    AdminSettingsView,
    AdminFlagResolveView,
    AuditLogDetailView,
    AuditLogListView,
    DashboardOrdersByMonthView,
    DashboardView,
    PublicConfigView,
    ReportExportView,
    ReportSummaryView,
)

urlpatterns = [
    path("public/config/", PublicConfigView.as_view(), name="public-config"),
    path("admin/dashboard/", DashboardView.as_view(), name="admin-dashboard"),
    path(
        "admin/dashboard/orders-by-day/",
        DashboardOrdersByMonthView.as_view(),
        name="admin-dashboard-orders-by-day",
    ),
    path("admin/reports/summary/", ReportSummaryView.as_view(), name="admin-report-summary"),
    path("admin/reports/export/", ReportExportView.as_view(), name="admin-report-export"),
    path("admin/settings/", AdminSettingsView.as_view(), name="admin-settings"),
    path("admin/flags/", AdminFlagListView.as_view(), name="admin-flag-list"),
    path("admin/flags/<int:id>/resolve/", AdminFlagResolveView.as_view(), name="admin-flag-resolve"),
    path("admin/audit-logs/", AuditLogListView.as_view(), name="admin-audit-log-list"),
    path("admin/audit-logs/<int:id>/", AuditLogDetailView.as_view(), name="admin-audit-log-detail"),
    path(
        "admin/audit-trail/<str:model>/<int:id>/",
        AdminChangeLogView.as_view(),
        name="admin-change-log",
    ),
]
