from django.urls import path

from reviews.farmer.views_farmer import FarmerReviewListView, FarmerReviewReplyView, ProductReviewReplyView

urlpatterns = [
    path("reviews/", FarmerReviewListView.as_view(), name="farmer-reviews-list"),
    path("farmer-reviews/<int:review_id>/reply/", FarmerReviewReplyView.as_view(), name="farmer-review-reply"),
    path("product-reviews/<int:review_id>/reply/", ProductReviewReplyView.as_view(), name="product-review-reply"),
]
