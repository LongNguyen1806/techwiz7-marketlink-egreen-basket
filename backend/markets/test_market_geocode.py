"""The market form asks the server where an address is, then the admin fine-tunes the pin."""

from decimal import Decimal

import pytest
from django.urls import reverse

from markets.admin_portal import views_admin

URL_NAME = "admin-market-geocode"


@pytest.mark.django_db
class TestGeocode:
    def test_returns_the_coordinates_found(self, admin_client, monkeypatch):
        seen = []

        def fake(address):
            seen.append(address)
            return Decimal("10.772500"), Decimal("106.698000")

        monkeypatch.setattr(views_admin, "geocode_address", fake)

        response = admin_client.get(reverse(URL_NAME), {"q": "  Ben Thanh Market, District 1  "})

        assert response.status_code == 200
        assert response.data["data"] == {"found": True, "latitude": 10.7725, "longitude": 106.698}
        assert seen == ["Ben Thanh Market, District 1"]

    def test_says_so_when_nothing_is_found(self, admin_client, monkeypatch):
        monkeypatch.setattr(views_admin, "geocode_address", lambda address: None)

        response = admin_client.get(reverse(URL_NAME), {"q": "Nowhere Street 999"})

        assert response.status_code == 200
        assert response.data["data"]["found"] is False
        assert response.data["data"]["latitude"] is None

    def test_a_too_short_query_is_refused_without_a_lookup(self, admin_client, monkeypatch):
        def fail(address):
            raise AssertionError("must not look up")

        monkeypatch.setattr(views_admin, "geocode_address", fail)

        response = admin_client.get(reverse(URL_NAME), {"q": "ab"})

        assert response.status_code == 400
        assert "q" in response.data["errors"]

    def test_only_admins_may_look_up(self, api_client):
        response = api_client.get(reverse(URL_NAME), {"q": "Ben Thanh Market"})

        assert response.status_code in (401, 403)
