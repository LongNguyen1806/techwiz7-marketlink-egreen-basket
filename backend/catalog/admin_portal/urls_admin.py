from django.urls import path

from catalog.admin_portal.views_admin import (
    AIReviewStatsView,
    PriceGuidelineDetailView,
    PriceGuidelineListCreateView,
    ProductAIRecheckView,
    CategoryDetailView,
    CategoryListCreateView,
    ProductApproveView,
    ProductBlockImpactView,
    ProductBlockView,
    ProductHideView,
    ProductModerationListView,
    ProductRejectView,
    ProductRestoreView,
    ProductUnblockView,
)

urlpatterns = [
    path("admin/categories/", CategoryListCreateView.as_view(), name="admin-category-list"),
    path("admin/categories/<int:id>/", CategoryDetailView.as_view(), name="admin-category-detail"),
    path("admin/products/", ProductModerationListView.as_view(), name="admin-product-list"),
    path("admin/products/<int:id>/ai-recheck/", ProductAIRecheckView.as_view(), name="admin-product-ai-recheck"),
    path("admin/price-guidelines/", PriceGuidelineListCreateView.as_view(), name="admin-price-guideline-list"),
    path("admin/price-guidelines/<int:id>/", PriceGuidelineDetailView.as_view(), name="admin-price-guideline-detail"),
    path("admin/ai-review/stats/", AIReviewStatsView.as_view(), name="admin-ai-review-stats"),
    path(
        "admin/products/<int:id>/approve/",
        ProductApproveView.as_view(),
        name="admin-product-approve",
    ),
    path(
        "admin/products/<int:id>/reject/",
        ProductRejectView.as_view(),
        name="admin-product-reject",
    ),
    path("admin/products/<int:id>/hide/", ProductHideView.as_view(), name="admin-product-hide"),
    path(
        "admin/products/<int:id>/restore/",
        ProductRestoreView.as_view(),
        name="admin-product-restore",
    ),
    path(
        "admin/products/<int:id>/block-impact/",
        ProductBlockImpactView.as_view(),
        name="admin-product-block-impact",
    ),
    path("admin/products/<int:id>/block/", ProductBlockView.as_view(), name="admin-product-block"),
    path(
        "admin/products/<int:id>/unblock/",
        ProductUnblockView.as_view(),
        name="admin-product-unblock",
    ),
]
