from rest_framework import serializers

from reviews.display import short_customer_name
from reviews.selectors import ReviewType


class PublicReviewSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    type = serializers.ChoiceField(choices=ReviewType.choices, read_only=True)
    rating = serializers.IntegerField(read_only=True)
    comment = serializers.CharField(read_only=True, allow_null=True)
    customer_display_name = serializers.CharField(read_only=True)
    product = serializers.DictField(read_only=True, allow_null=True)
    reply = serializers.CharField(read_only=True, allow_null=True)
    replied_at = serializers.DateTimeField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)


class RatingSummarySerializer(serializers.Serializer):
    rating_avg = serializers.FloatField(allow_null=True)
    rating_count = serializers.IntegerField()
    distribution = serializers.DictField(child=serializers.IntegerField())


def serialize_public_review(review_type: str, review) -> dict:
    if review_type == ReviewType.PRODUCT:
        order = review.order_item.order
        product = {"id": review.order_item.product_id, "name": review.order_item.product.name}
    else:
        order = review.order
        product = None
    profile = getattr(order.customer, "customer_profile", None)
    return {
        "id": review.pk,
        "type": review_type,
        "rating": review.rating,
        "comment": review.comment,
        "customer_display_name": short_customer_name(getattr(profile, "full_name", None)),
        "product": product,
        "reply": review.reply,
        "replied_at": review.replied_at,
        "created_at": review.created_at,
    }
