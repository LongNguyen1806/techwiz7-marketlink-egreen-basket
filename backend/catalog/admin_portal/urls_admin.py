from django.urls import path

from catalog.admin_portal.views_admin import (
    CategoryDetailView,
    CategoryListCreateView,
    ProductBlockImpactView,
    ProductBlockView,
    ProductHideView,
    ProductModerationListView,
    ProductRestoreView,
    ProductUnblockView,
)

urlpatterns = [
    path("admin/categories/", CategoryListCreateView.as_view(), name="admin-category-list"),
    path("admin/categories/<int:id>/", CategoryDetailView.as_view(), name="admin-category-detail"),
    path("admin/products/", ProductModerationListView.as_view(), name="admin-product-list"),
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
