"""The rule layer: word matching (with the Vietnamese pitfalls) and the number checks."""

from decimal import Decimal

import pytest

from catalog.ai_review import wordlists
from catalog.ai_review.rules import run_rules
from catalog.ai_review.types import ListingInput, verdict_for
from catalog.models import AIVerdict, PriceGuideline, Product, ReviewStatus, Unit


def _listing(category=None, **overrides) -> ListingInput:
    fields = {
        "name": "Organic Tomato",
        "description": "",
        "category_id": category.pk if category else None,
        "category_name": category.name if category else "Vegetables",
        "unit": Unit.KG,
        "price": Decimal("2.50"),
        "stock_quantity": 40,
    }
    fields.update(overrides)
    return ListingInput(**fields)


def _checks(findings) -> set[str]:
    return {finding.check for finding in findings}




@pytest.mark.parametrize(
    "text",
    ["Bưởi da xanh", "Quả sung chín", "Cà chua lớn", "Grass-fed beef", "Assam tea", "Carrot", "Scarlet cabbage", "A B grade"],
)
def test_produce_words_that_look_like_bad_words_are_not_flagged(text):
    assert wordlists.find_profanity(text) == []
    assert wordlists.find_prohibited(text) == []


@pytest.mark.parametrize("text", ["Fucking good", "sh1t mango", "f.u.c.k", "Rau đ.m", "d i t m e", "Rau lồn", "VCL rẻ"])
def test_swearing_is_found_through_marks_dots_spaces_and_leetspeak(text):
    assert wordlists.find_profanity(text)


@pytest.mark.parametrize("text", ["Honda Wave cũ", "Xe máy chính chủ", "iPhone 12", "Súng nhựa", "cần sa khô"])
def test_items_a_market_cannot_sell_are_found(text):
    assert wordlists.find_prohibited(text)


@pytest.mark.parametrize(
    ("text", "kind"),
    [("Call 0901 234 567", "phone number"), ("mail me a@b.vn", "email address"), ("www.shop.vn", "web link"), ("add zalo", "messaging app")],
)
def test_off_platform_contact_is_found(text, kind):
    assert kind in wordlists.find_contact(text)


def test_prices_and_weights_are_not_mistaken_for_a_phone_number():
    assert wordlists.find_contact("12.50 per 1000g, 5 kg bags") == []




@pytest.fixture
def guideline(category):
    return PriceGuideline.objects.create(
        category=category, unit=Unit.KG, min_price=Decimal("0.20"), max_price=Decimal("20.00"), max_stock=5000
    )


def test_a_price_inside_the_guideline_passes(guideline, category):
    assert verdict_for(run_rules(_listing(category))) == AIVerdict.PASS


def test_a_price_outside_the_guideline_needs_a_look(guideline, category):
    findings = run_rules(_listing(category, price=Decimal("25.00")))
    assert "PRICE_OUT_OF_RANGE" in _checks(findings)
    assert verdict_for(findings) == AIVerdict.NEEDS_REVIEW


def test_a_price_far_outside_the_guideline_is_a_likely_violation(guideline, category):
    findings = run_rules(_listing(category, price=Decimal("9999.00")))
    assert verdict_for(findings) == AIVerdict.LIKELY_VIOLATION


def test_stock_above_the_guideline_is_unusual(guideline, category):
    assert "STOCK_UNUSUAL" in _checks(run_rules(_listing(category, stock_quantity=90000)))


def test_price_far_from_what_other_stalls_charge_is_flagged(category, approved_farmer):
    for price in ("2.00", "2.20", "2.50", "2.80", "3.00"):
        Product.objects.create(
            farmer=approved_farmer, category=category, name="Peer", price=price, unit=Unit.KG,
            stock_quantity=5, review_status=ReviewStatus.APPROVED,
        )
    assert "PRICE_UNLIKE_PEERS" in _checks(run_rules(_listing(category, price=Decimal("15.00"))))
    assert "PRICE_UNLIKE_PEERS" not in _checks(run_rules(_listing(category, price=Decimal("3.50"))))


def test_the_peer_check_waits_for_enough_listings(category, approved_farmer):
    Product.objects.create(
        farmer=approved_farmer, category=category, name="Peer", price="2.00", unit=Unit.KG,
        stock_quantity=5, review_status=ReviewStatus.APPROVED,
    )
    assert "PRICE_UNLIKE_PEERS" not in _checks(run_rules(_listing(category, price=Decimal("15.00"))))


def test_a_minimum_above_the_stock_is_pointed_out(category):
    assert "MIN_ABOVE_STOCK" in _checks(run_rules(_listing(category, stock_quantity=3, min_per_order=5)))
