from django.urls import path

from accounts.public_portal.views_public import (
    GeocodeView,
    PublicFarmerDetailView,
    PublicFarmerListView,
)
from reviews.public_portal.views_public import PublicFarmerReviewListView

urlpatterns = [
    path("public/geocode/", GeocodeView.as_view(), name="public-geocode"),
    path("public/farmers/", PublicFarmerListView.as_view(), name="public-farmer-list"),
    path("public/farmers/<int:id>/", PublicFarmerDetailView.as_view(), name="public-farmer-detail"),
    path(
        "public/farmers/<int:id>/reviews/",
        PublicFarmerReviewListView.as_view(),
        name="public-farmer-review-list",
    ),
]
