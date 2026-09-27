import pytest
from django.contrib.auth import get_user_model
from django.core.cache import caches
from rest_framework.test import APIClient

from accounts.models import CustomerProfile, FarmerProfile, FarmerStatus, Role
from marketlink_core.policies.roles import RoleCode

User = get_user_model()

PASSWORD = "Str0ngPass123"


def _clear_all_caches():
    for alias in caches:
        caches[alias].clear()


@pytest.fixture(autouse=True)
def _no_real_ai_calls(settings):
    # A GEMINI_API_KEY in .env must never make the test suite call the real model (cost, and
    # answers that change run to run). AI tests stub catalog.ai_review.gemini.ask_model.
    settings.GEMINI_API_KEY = ""
    settings.AI_MODERATION_RUN_INLINE = True
    settings.AI_MODERATION_BATCH_PAUSE_MS = 0


@pytest.fixture(autouse=True)
def _clear_caches():
    # Throttle counters live in "default"; token revocation lives in "blacklist".
    _clear_all_caches()
    yield
    _clear_all_caches()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin@marketlink.test",
        password=PASSWORD,
        role=Role.objects.get(code=RoleCode.ADMIN),
        is_staff=True,
    )


@pytest.fixture
def customer_user(db):
    user = User.objects.create_user(
        email="customer@marketlink.test",
        password=PASSWORD,
        role=Role.objects.get(code=RoleCode.CUSTOMER),
    )
    CustomerProfile.objects.create(
        user=user, full_name="Test Customer", phone="0901234567", address="12 Test Street",
    )
    return user


@pytest.fixture
def farmer_user(db):
    user = User.objects.create_user(
        email="farmer@marketlink.test",
        password=PASSWORD,
        role=Role.objects.get(code=RoleCode.FARMER),
    )
    FarmerProfile.objects.create(
        user=user,
        stall_name="Test Stall",
        contact_person="Test Farmer",
        phone="0907654321",
        address="34 Market Street",
        # D-031 requires at least one operating day; open all week so a fixture never makes a
        # test depend on which weekday it runs on.
        operating_days=[1, 2, 3, 4, 5, 6, 7],
    )
    return user


@pytest.fixture
def make_farmer(db):
    def _make(*, email: str, stall_name: str, status: str = FarmerStatus.PENDING) -> FarmerProfile:
        user = User.objects.create_user(
            email=email, password="Str0ngPass123", role=Role.objects.get(code=RoleCode.FARMER)
        )
        return FarmerProfile.objects.create(
            user=user,
            stall_name=stall_name,
            contact_person="Contact Person",
            phone=f"09{user.pk:08d}",
            address="1 Farm Road",
            status=status,
            operating_days=[1, 2, 3, 4, 5, 6, 7],  # D-031: at least one day is mandatory.
        )

    return _make


@pytest.fixture
def admin_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def customer_client(api_client, customer_user):
    api_client.force_authenticate(user=customer_user)
    return api_client
