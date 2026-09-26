from django.urls import path

from system.views import (
    AdminChangeLogView,
    AuditLogDetailView,
    AuditLogListView,
    DashboardView,
    PublicConfigView,
    ReportExportView,
    ReportSummaryView,
)

urlpatterns = [
    path("public/config/", PublicConfigView.as_view(), name="public-config"),
    path("admin/dashboard/", DashboardView.as_view(), name="admin-dashboard"),
    path("admin/reports/summary/", ReportSummaryView.as_view(), name="admin-report-summary"),
    path("admin/reports/export/", ReportExportView.as_view(), name="admin-report-export"),
    path("admin/audit-logs/", AuditLogListView.as_view(), name="admin-audit-log-list"),
    path("admin/audit-logs/<int:id>/", AuditLogDetailView.as_view(), name="admin-audit-log-detail"),
    path(
        "admin/audit-trail/<str:model>/<int:id>/",
        AdminChangeLogView.as_view(),
        name="admin-change-log",
    ),
]
