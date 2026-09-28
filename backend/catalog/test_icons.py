"""The icon list lives twice, in catalog/icons.py and in the frontend's categoryIcon.js."""

import re
from pathlib import Path

import pytest
from django.urls import reverse

from catalog.icons import CATEGORY_ICONS, LEGACY_ICON_ALIASES

FRONTEND_ICONS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "utils" / "categoryIcon.js"


def _frontend_names() -> set[str]:
    source = FRONTEND_ICONS.read_text(encoding="utf-8")
    body = source.split("const ICONS = {", 1)[1].split("};", 1)[0]
    return set(re.findall(r"^\s*'?([a-z][a-z-]*)'?\s*:", body, re.M))


@pytest.mark.skipif(not FRONTEND_ICONS.exists(), reason="frontend not checked out next to backend")
def test_every_icon_the_server_accepts_has_a_picture_and_the_other_way_round():
    assert set(CATEGORY_ICONS) == _frontend_names()


def test_names_are_unique_and_never_shadowed_by_an_old_alias():
    assert len(CATEGORY_ICONS) == len(set(CATEGORY_ICONS))
    assert not set(CATEGORY_ICONS) & set(LEGACY_ICON_ALIASES)


@pytest.mark.django_db
@pytest.mark.parametrize("icon", ["tomato", "bell-pepper", "poultry"])
def test_a_category_can_wear_one_of_the_new_icons(admin_client, icon):
    response = admin_client.post(
        reverse("admin-category-list"), {"name": f"Test {icon}", "icon": icon}, format="json"
    )

    assert response.status_code == 201, response.data
    assert response.data["data"]["icon"] == icon
