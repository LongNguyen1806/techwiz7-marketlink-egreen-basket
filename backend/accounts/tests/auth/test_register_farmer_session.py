import pytest

from accounts.tests.auth.conftest import bearer

URL = "/api/auth/register/farmer/"
BODY = {
    "email": "stall@example.com",
    "password": "Garden2026x",
    "confirm_password": "Garden2026x",
    "stall_name": "Sunrise Stall",
    "contact_person": "Tran Van Binh",
    "phone": "0977000111",
    "address": "8 Market Lane, District 3",
    "operating_days": [2, 4, 6],
}


@pytest.fixture(autouse=True)
def _no_geocoding(settings):
    settings.GEOCODING_ENABLED = False


def _register(api, **overrides):
    return api.post(URL, {**BODY, **overrides}, format="json")


@pytest.mark.django_db
class TestFarmerSignUpStartsASession:
    """AU-02 signs the farmer in with the same session tokens as AU-01 / AU-03 (P2: sid + pwv claims)."""

    def test_access_token_works_right_away(self, api):
        data = _register(api).json()["data"]

        me = api.get("/api/auth/me/", **bearer(data["access"]))

        assert me.status_code == 200
        assert (me.json()["data"]["role"], me.json()["data"]["farmer_status"]) == ("FARMER", "PENDING")

    def test_refresh_token_rotates(self, api):
        data = _register(api).json()["data"]

        response = api.post("/api/auth/refresh/", {"refresh": data["refresh"]}, format="json")

        assert response.status_code == 200

    def test_logout_ends_the_sign_up_session(self, api):
        data = _register(api).json()["data"]
        api.post("/api/auth/logout/", {"refresh": data["refresh"]}, format="json", **bearer(data["access"]))

        assert api.get("/api/auth/me/", **bearer(data["access"])).status_code == 401

    def test_me_shape_matches_the_other_portals(self, api):
        user = _register(api).json()["data"]["user"]

        assert set(user) == {"id", "email", "role", "display_name", "farmer_status", "avatar"}
        assert user["display_name"] == "Sunrise Stall"


@pytest.mark.django_db
class TestFarmerPasswordRulesMatchCustomers:
    """AU-02 uses the same password rule as AU-01 (check_password_strength, incl. Django's validators)."""

    @pytest.mark.parametrize("password", ["short1", "lettersonly", "12345678", "password123"])
    def test_weak_password_is_rejected(self, api, password):
        response = _register(api, password=password, confirm_password=password)

        assert (response.status_code, response.json()["code"]) == (400, "VALIDATION_ERROR")
        assert "password" in response.json()["errors"]
