from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from catalog.services.farmer_product import validate_image_upload
from marketlink_core.exceptions import BusinessValidationError
from markets.models import DayOfWeek, Market
from markets.serializers import ClosureSerializer
from markets.selectors import OPERATING_DAYS_ATTR, UPCOMING_CLOSURES_ATTR, today

NAME_MIN_LENGTH = 2
NAME_MAX_LENGTH = 100
ADDRESS_MIN_LENGTH = 5
ADDRESS_MAX_LENGTH = 255
DESCRIPTION_MAX_LENGTH = 1000
DUPLICATE_NAME_MESSAGE = "A market with this name already exists."


class ClosureWriteSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    reason = serializers.CharField(max_length=200, required=False, allow_null=True, allow_blank=True)

    def validate_start_date(self, value):
        if value < today():
            raise serializers.ValidationError("A closure cannot start in the past.")
        return value

    def validate(self, attrs):
        if attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError(
                {"end_date": "The end date cannot be earlier than the start date."}
            )
        return attrs


class MarketAdminReadSerializer(serializers.ModelSerializer):
    operating_days = serializers.SerializerMethodField()
    upcoming_closures = serializers.SerializerMethodField()
    open_time = serializers.TimeField(format="%H:%M")
    close_time = serializers.TimeField(format="%H:%M")
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    farmer_count = serializers.IntegerField(read_only=True, default=0)
    open_order_count = serializers.IntegerField(read_only=True, default=0)
    distance_km = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()

    class Meta:
        model = Market
        fields = [
            "id",
            "name",
            "address",
            "description",
            "image",
            "latitude",
            "longitude",
            "map_provider",
            "operating_days",
            "open_time",
            "close_time",
            "upcoming_closures",
            "farmer_count",
            "distance_km",
            "is_favorite",
            "is_active",
            "open_order_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    @staticmethod
    def _prefetched(market, attr, fallback):
        rows = getattr(market, attr, None)
        return rows if rows is not None else fallback()

    def get_operating_days(self, market) -> list[int]:
        rows = self._prefetched(
            market,
            OPERATING_DAYS_ATTR,
            lambda: market.operating_days.order_by("day_of_week"),
        )
        return [row.day_of_week for row in rows]

    def get_upcoming_closures(self, market) -> list[dict]:
        rows = self._prefetched(
            market,
            UPCOMING_CLOSURES_ATTR,
            lambda: market.closures.filter(end_date__gte=today()).order_by("start_date"),
        )
        return ClosureSerializer(rows, many=True).data

    # A bare `-> None` hint tells the schema generator nothing, so the nullable type
    # each field keeps in MarketSummary is declared explicitly.
    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_distance_km(self, market):
        return None

    @extend_schema_field(serializers.BooleanField(allow_null=True))
    def get_is_favorite(self, market):
        return None


class MarketAdminWriteSerializer(serializers.ModelSerializer):
    # Declaring `name` replaces the auto-built field and with it the model's
    # UniqueValidator, so it is restored explicitly. The lookup runs under the column's
    # utf8mb4_0900_as_ci collation: accent-sensitive, case-insensitive.
    name = serializers.CharField(
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
        validators=[UniqueValidator(queryset=Market.objects.all(), message=DUPLICATE_NAME_MESSAGE)],
    )
    address = serializers.CharField(min_length=ADDRESS_MIN_LENGTH, max_length=ADDRESS_MAX_LENGTH)
    description = serializers.CharField(
        max_length=DESCRIPTION_MAX_LENGTH, required=False, allow_null=True, allow_blank=True
    )
    operating_days = serializers.ListField(
        child=serializers.ChoiceField(choices=DayOfWeek.choices),
        min_length=1,
        help_text="ISO weekday numbers, 1 = Monday through 7 = Sunday.",
    )
    image = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = Market
        fields = [
            "name",
            "address",
            "description",
            "image",
            "latitude",
            "longitude",
            "operating_days",
            "open_time",
            "close_time",
        ]

    def validate_name(self, value: str) -> str:
        return value.strip()

    def validate_image(self, value):
        # NFR-01: same checks as farmer uploads (type, 2MB, real content); the re-encoded copy is stored.
        if not value:
            return value
        try:
            return validate_image_upload(value)
        except BusinessValidationError as exc:
            raise serializers.ValidationError(exc.errors.get("image", [str(exc.detail)])) from None

    def validate(self, attrs):
        instance = self.instance
        open_time = attrs.get("open_time", getattr(instance, "open_time", None))
        close_time = attrs.get("close_time", getattr(instance, "close_time", None))
        if open_time is not None and close_time is not None and close_time <= open_time:
            raise serializers.ValidationError(
                {"close_time": "The closing time must be later than the opening time."}
            )
        return attrs
