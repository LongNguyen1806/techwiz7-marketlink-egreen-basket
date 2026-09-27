from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from simple_history.models import HistoricalRecords

from marketlink_core.models import BaseModel, HistoryRequestMeta, UUIDUploadTo


class DayOfWeek(models.IntegerChoices):
    MONDAY = 1, "Monday"
    TUESDAY = 2, "Tuesday"
    WEDNESDAY = 3, "Wednesday"
    THURSDAY = 4, "Thursday"
    FRIDAY = 5, "Friday"
    SATURDAY = 6, "Saturday"
    SUNDAY = 7, "Sunday"


class Market(BaseModel):
    name = models.CharField(max_length=100, unique=True, db_collation="utf8mb4_0900_as_ci")
    address = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    image = models.ImageField(
        upload_to=UUIDUploadTo("markets"), max_length=255, null=True, blank=True
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("90"))],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(Decimal("-180")), MaxValueValidator(Decimal("180"))],
    )
    map_provider = models.CharField(max_length=30, default="OSM")
    open_time = models.TimeField()
    close_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "markets"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active"], name="market_active_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(close_time__gt=F("open_time")),
                name="market_close_after_open",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class MarketOperatingDay(BaseModel):
    market = models.ForeignKey(Market, on_delete=models.CASCADE, related_name="operating_days")
    day_of_week = models.PositiveSmallIntegerField(choices=DayOfWeek.choices)

    class Meta:
        db_table = "market_operating_days"
        ordering = ["market_id", "day_of_week"]
        indexes = [
            models.Index(fields=["day_of_week"], name="mod_day_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["market", "day_of_week"], name="mod_uniq_market_day"),
            models.CheckConstraint(
                condition=Q(day_of_week__gte=1, day_of_week__lte=7),
                name="mod_day_1_7",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.market_id} - {self.get_day_of_week_display()}"


class FarmerMarket(BaseModel):
    farmer = models.ForeignKey(
        "accounts.FarmerProfile", on_delete=models.CASCADE, related_name="farmer_markets"
    )
    market = models.ForeignKey(Market, on_delete=models.RESTRICT, related_name="farmer_markets")
    stall_label = models.CharField(max_length=100)

    history = HistoricalRecords(
        table_name="farmer_market_histories",
        bases=[HistoryRequestMeta],
    )

    class Meta:
        db_table = "farmer_markets"
        constraints = [
            # A stall trades at exactly one market; moving elsewhere is a fresh registration.
            # Unique on the farmer alone, which also subsumes the old (farmer, market) pair
            # constraint, so that one is gone rather than left as a second index saying less.
            models.UniqueConstraint(fields=["farmer"], name="fm_uniq_farmer"),
        ]

    def __str__(self) -> str:
        return f"{self.farmer_id} @ {self.market_id}"


class PickupSlot(BaseModel):
    farmer_market = models.ForeignKey(
        FarmerMarket, on_delete=models.CASCADE, related_name="pickup_slots"
    )
    day_of_week = models.PositiveSmallIntegerField(choices=DayOfWeek.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords(
        table_name="pickup_slot_histories",
        bases=[HistoryRequestMeta],
    )

    class Meta:
        db_table = "pickup_slots"
        ordering = ["farmer_market_id", "day_of_week", "start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["farmer_market", "day_of_week", "start_time"],
                name="slot_uniq_fm_day_start",
            ),
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")),
                name="slot_end_after_start",
            ),
            models.CheckConstraint(
                condition=Q(day_of_week__gte=1, day_of_week__lte=7),
                name="slot_day_1_7",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_day_of_week_display()} {self.start_time}-{self.end_time}"


class ClosureFields(BaseModel):
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        abstract = True


class MarketClosure(ClosureFields):
    market = models.ForeignKey(Market, on_delete=models.CASCADE, related_name="closures")

    class Meta:
        db_table = "market_closures"
        ordering = ["start_date"]
        indexes = [
            models.Index(fields=["market", "end_date"], name="mclosure_market_end_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__gte=F("start_date")),
                name="mclosure_end_after_start",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.market_id}: {self.start_date} -> {self.end_date}"


class FarmerClosure(ClosureFields):
    farmer = models.ForeignKey(
        "accounts.FarmerProfile", on_delete=models.CASCADE, related_name="closures"
    )

    history = HistoricalRecords(
        table_name="farmer_closure_histories",
        bases=[HistoryRequestMeta],
    )

    class Meta:
        db_table = "farmer_closures"
        ordering = ["start_date"]
        indexes = [
            models.Index(fields=["farmer", "end_date"], name="fclosure_farmer_end_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__gte=F("start_date")),
                name="fclosure_end_after_start",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.farmer_id}: {self.start_date} -> {self.end_date}"
