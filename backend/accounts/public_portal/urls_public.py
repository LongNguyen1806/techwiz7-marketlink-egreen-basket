from django.urls import path

from accounts.public_portal.views_public import (
    GeocodeView,
    PublicFarmerDetailView,
    PublicFarmerListView,
)
from reviews.public_portal.views_public import PublicFarmerReviewListView

# PU-08 pickup-options belongs to the Customer branch; it gets its own url module so this
# file is not edited by two branches at once.
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
