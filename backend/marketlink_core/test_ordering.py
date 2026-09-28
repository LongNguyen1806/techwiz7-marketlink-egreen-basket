import pytest

from marketlink_core.exceptions import BusinessValidationError, ErrorCode
from marketlink_core.ordering import both_directions, resolve_ordering

ALLOWED = both_directions({"name": ("stall_name",), "joined": ("date_joined",)}, tiebreak=("-id",))
ALLOWED["newest"] = ("-date_joined",)


def test_blank_or_missing_falls_back_to_the_default():
    assert resolve_ordering(None, allowed=ALLOWED, default="newest") == ("-date_joined",)
    assert resolve_ordering("   ", allowed=ALLOWED, default="newest") == ("-date_joined",)


def test_a_known_key_maps_to_its_columns():
    assert resolve_ordering("name", allowed=ALLOWED, default="name") == ("stall_name", "-id")


def test_descending_flips_every_column_but_keeps_the_tiebreak():
    expanded = both_directions({"rank": ("score", "-name")}, tiebreak=("-id",))
    assert expanded["rank"] == ("score", "-name", "-id")
    assert expanded["-rank"] == ("-score", "name", "-id")


def test_an_unknown_key_is_rejected_rather_than_ignored():
    with pytest.raises(BusinessValidationError) as exc:
        resolve_ordering("password", allowed=ALLOWED, default="name")
    assert exc.value.code == ErrorCode.VALIDATION_ERROR
    assert exc.value.status_code == 400
    assert "ordering" in exc.value.errors


def test_a_column_not_on_the_list_cannot_be_smuggled_in_backwards():
    with pytest.raises(BusinessValidationError):
        resolve_ordering("-password", allowed=ALLOWED, default="name")


def test_expressions_are_refused_so_they_are_spelt_out_by_hand():
    from django.db.models import F

    with pytest.raises(TypeError):
        both_directions({"rating": (F("rating_avg").desc(nulls_last=True),)})
