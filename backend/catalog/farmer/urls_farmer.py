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
    # FA-17 & FA-18 (Weekly template preview & apply)
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
    # Rule checks while the farmer fills in the product form (advice only).
    path("precheck/", FarmerProductPrecheckView.as_view(), name="product-precheck"),
    path("counts/", FarmerProductCountsView.as_view(), name="product-counts"),
    path("bulk/", FarmerProductBulkView.as_view(), name="product-bulk"),
    # FA-11 & FA-12 (List & Create)
    path("", FarmerProductListView.as_view(), name="product-list"),
    # FA-16 (Quick Mark Sold Out)
    path(
        "<int:pk>/mark-sold-out/",
        FarmerProductMarkSoldOutView.as_view(),
        name="product-mark-sold-out",
    ),
    # FA-13, FA-14, FA-15 (Detail, Update, Soft Delete)
    path("<int:pk>/", FarmerProductDetailView.as_view(), name="product-detail"),
]
