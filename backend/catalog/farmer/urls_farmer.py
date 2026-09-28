from django.urls import path

from catalog.farmer.views_farmer import (
    FarmerProductBulkView,
    FarmerProductCountsView,
    FarmerProductDetailView,
    FarmerProductListView,
    FarmerProductMarkSoldOutView,
    FarmerProductPrecheckView,
    FarmerWeeklyTemplateApplyView,
    FarmerWeeklyTemplatePreviewView,
)

app_name = "catalog_farmer"

urlpatterns = [
    path(
        "weekly-template-preview/",
        FarmerWeeklyTemplatePreviewView.as_view(),
        name="weekly-template-preview",
    ),
    path(
        "apply-weekly-template/",
        FarmerWeeklyTemplateApplyView.as_view(),
        name="apply-weekly-template",
    ),
    path("precheck/", FarmerProductPrecheckView.as_view(), name="product-precheck"),
    path("counts/", FarmerProductCountsView.as_view(), name="product-counts"),
    path("bulk/", FarmerProductBulkView.as_view(), name="product-bulk"),
    path("", FarmerProductListView.as_view(), name="product-list"),
    path(
        "<int:pk>/mark-sold-out/",
        FarmerProductMarkSoldOutView.as_view(),
        name="product-mark-sold-out",
    ),
    path("<int:pk>/", FarmerProductDetailView.as_view(), name="product-detail"),
]
