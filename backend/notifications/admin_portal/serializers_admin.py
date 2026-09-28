from rest_framework import serializers

from notifications.models import Announcement

TITLE_MIN_LENGTH = 5
TITLE_MAX_LENGTH = 150
CONTENT_MAX_LENGTH = 1000


class AnnouncementAdminReadSerializer(serializers.ModelSerializer):
    created_by_name = serializers.EmailField(source="created_by.email", read_only=True, default=None)

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "content",
            "audience",
            "starts_at",
            "ends_at",
            "is_active",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class AnnouncementAdminWriteSerializer(serializers.ModelSerializer):
    title = serializers.CharField(min_length=TITLE_MIN_LENGTH, max_length=TITLE_MAX_LENGTH)
    content = serializers.CharField(max_length=CONTENT_MAX_LENGTH)

    class Meta:
        model = Announcement
        fields = ["title", "content", "audience", "starts_at", "ends_at", "is_active"]

    def validate(self, attrs: dict) -> dict:
        starts_at = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends_at = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if starts_at and ends_at and ends_at <= starts_at:
            raise serializers.ValidationError(
                {"ends_at": ["The end time must be after the start time."]}
            )
        return attrs
