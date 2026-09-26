from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from simple_history.models import HistoricalRecords

from accounts.operating_days import normalize_operating_days
from accounts.phone import normalize_phone
from marketlink_core.models import BaseModel, HistoryRequestMeta, UUIDUploadTo
from marketlink_core.policies.roles import RoleCode


class Role(BaseModel):
    code = models.CharField(
        max_length=50,
        unique=True,
        choices=RoleCode.choices,
        db_collation="utf8mb4_0900_as_ci",
    )
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "roles"
        ordering = ["id"]

    def __str__(self) -> str:
        return self.code


class CustomUserManager(BaseUserManager):
    use_in_migrations = True

    @staticmethod
    def _clean_email(email: str | None) -> str:
        if not email:
            raise ValueError("Email is required.")
        return email.strip().lower()

    def create_user(self, email, password=None, **extra_fields):
        email = self._clean_email(email)
        if extra_fields.get("role") is None and extra_fields.get("role_id") is None:
            raise ValueError("Role is required for user creation.")
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True or extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_staff=True and is_superuser=True.")
        try:
            extra_fields["role"] = Role.objects.get(code=RoleCode.ADMIN)
        except Role.DoesNotExist as exc:
            raise ValueError(
                "Role ADMIN does not exist. Run migration seed first."
            ) from exc
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    username = None
    first_name = None
    last_name = None

    email = models.EmailField(max_length=100, unique=True)
    role = models.ForeignKey(Role, on_delete=models.RESTRICT, related_name="users")
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = CustomUserManager()

    class Meta:
        db_table = "users"
        indexes = [
            models.Index(fields=["role", "is_active"], name="users_role_active_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def get_full_name(self) -> str:
        return self.email

    def get_short_name(self) -> str:
        return self.email

    def __str__(self) -> str:
        return self.email


LATITUDE_VALIDATORS = [MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("90"))]
LONGITUDE_VALIDATORS = [MinValueValidator(Decimal("-180")), MaxValueValidator(Decimal("180"))]


class CustomerProfile(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="customer_profile",
    )
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, unique=True)
    address = models.CharField(max_length=255)
    # Plural folder name to match farmers/ , markets/ and products/ already in use.
    image = models.ImageField(
        upload_to=UUIDUploadTo("customers"), max_length=255, null=True, blank=True
    )
    deactivation_reason = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        db_table = "customer_profiles"

    def __str__(self) -> str:
        return self.full_name

    def save(self, *args, **kwargs):
        self.phone = normalize_phone(self.phone)
        super().save(*args, **kwargs)


class FarmerStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    SUSPENDED = "SUSPENDED", "Suspended"
    REJECTED = "REJECTED", "Rejected"


class FarmerProfile(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="farmer_profile",
    )
    stall_name = models.CharField(max_length=100)
    contact_person = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, unique=True)
    address = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    image = models.ImageField(
        upload_to=UUIDUploadTo("farmers"), max_length=255, null=True, blank=True
    )
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True, validators=LATITUDE_VALIDATORS
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True, validators=LONGITUDE_VALIDATORS
    )
    status = models.CharField(
        max_length=20, choices=FarmerStatus.choices, default=FarmerStatus.PENDING
    )
    status_reason = models.CharField(max_length=500, null=True, blank=True)
    order_cutoff_hours = models.PositiveSmallIntegerField(
        default=12, validators=[MinValueValidator(1), MaxValueValidator(72)]
    )
    operating_days = models.JSONField(default=list)

    history = HistoricalRecords(
        table_name="farmer_profile_histories",
        bases=[HistoryRequestMeta],
    )

    class Meta:
        db_table = "farmer_profiles"
        indexes = [
            models.Index(fields=["status"], name="farmer_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(latitude__isnull=True, longitude__isnull=True)
                    | Q(latitude__isnull=False, longitude__isnull=False)
                ),
                name="farmer_coords_both_or_none",
            ),
            models.CheckConstraint(
                condition=Q(order_cutoff_hours__gte=1, order_cutoff_hours__lte=72),
                name="farmer_cutoff_hours_1_72",
            ),
        ]

    def __str__(self) -> str:
        return self.stall_name

    def clean(self):
        super().clean()
        # Admin forms call clean() first, so bad input shows as a form error instead of a 500.
        self.operating_days = normalize_operating_days(self.operating_days)

    def save(self, *args, **kwargs):
        self.phone = normalize_phone(self.phone)
        update_fields = kwargs.get("update_fields")
        # D-031: validate on every write of operating_days (seed, admin, API). A partial save that
        # does not touch the column (e.g. update_fields=["status"]) is not blocked by old data.
        if update_fields is None or "operating_days" in update_fields:
            self.operating_days = normalize_operating_days(self.operating_days)
        super().save(*args, **kwargs)
