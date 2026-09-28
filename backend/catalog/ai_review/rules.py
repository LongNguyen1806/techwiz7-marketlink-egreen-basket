"""The deterministic layer: instant, free, explainable, and run on every listing.

Numbers (price, unit, stock) are checked here and never by the model: a language model has no
reliable idea of today's market price and would answer differently each time. What the words
mean (offensive language, items that are not farm food, contact details to trade elsewhere) is
left to the model, which reads them in context (gemini.py).
"""

from decimal import Decimal
from statistics import median

from catalog.ai_review.types import Finding, ListingInput, Severity
from catalog.models import PriceGuideline, Product, ReviewStatus, Unit

RULES_VERSION = "rules-v1"

PEER_MINIMUM = 5
PEER_RATIO = Decimal("5")
GUIDELINE_FAR_RATIO = Decimal("10")

_UNIT_LABEL = {value: label.lower() for value, label in Unit.choices}


def _finding(check: str, severity: str, message: str) -> Finding:
    return Finding(source="rules", check=check, severity=severity, message=message)


def _unit(listing: ListingInput) -> str:
    return _UNIT_LABEL.get(listing.unit, listing.unit.lower())


def check_text(listing: ListingInput) -> list[Finding]:
    findings = []
    if listing.name and not any(ch.isalpha() for ch in listing.name):
        findings.append(_finding("NAME_QUALITY", Severity.LOW, "The name has no letters in it."))
    elif listing.name and listing.name.isupper() and len(listing.name) > 6:
        findings.append(_finding("NAME_QUALITY", Severity.LOW, "The name is written in capitals only."))
    return findings


def check_price(listing: ListingInput) -> list[Finding]:
    findings = []
    unit = _unit(listing)
    guideline = None
    if listing.category_id:
        guideline = PriceGuideline.objects.filter(category_id=listing.category_id, unit=listing.unit).first()

    if guideline is not None:
        price = listing.price
        if price < guideline.min_price or price > guideline.max_price:
            far = price > guideline.max_price * GUIDELINE_FAR_RATIO or price * GUIDELINE_FAR_RATIO < guideline.min_price
            findings.append(_finding(
                "PRICE_OUT_OF_RANGE", Severity.HIGH if far else Severity.MEDIUM,
                f"${price} per {unit} is outside the usual ${guideline.min_price}-${guideline.max_price} "
                f"for {listing.category_name} ({unit}).",
            ))
        if guideline.max_stock is not None and listing.stock_quantity > guideline.max_stock:
            findings.append(_finding(
                "STOCK_UNUSUAL", Severity.MEDIUM,
                f"Stock of {listing.stock_quantity} {unit} is above the usual {guideline.max_stock} "
                f"for {listing.category_name}.",
            ))

    peers = Product.objects.filter(
        category_id=listing.category_id,
        unit=listing.unit,
        is_archived=False,
        review_status=ReviewStatus.APPROVED,
    )
    if listing.product_id:
        peers = peers.exclude(pk=listing.product_id)
    prices = list(peers.values_list("price", flat=True)[:500])
    if len(prices) >= PEER_MINIMUM:
        typical = Decimal(median(prices))
        if typical > 0 and (listing.price > typical * PEER_RATIO or listing.price * PEER_RATIO < typical):
            findings.append(_finding(
                "PRICE_UNLIKE_PEERS", Severity.MEDIUM,
                f"${listing.price} per {unit} is far from the ${typical:.2f} other stalls typically charge "
                f"for {listing.category_name} ({unit}).",
            ))
    return findings


def check_quantities(listing: ListingInput) -> list[Finding]:
    unit = _unit(listing)
    if listing.stock_quantity and listing.min_per_order > listing.stock_quantity:
        return [_finding(
            "MIN_ABOVE_STOCK", Severity.LOW,
            f"The minimum per order ({listing.min_per_order} {unit}) is more than the stock "
            f"({listing.stock_quantity} {unit}), so nobody can order it.",
        )]
    return []


def run_rules(listing: ListingInput) -> list[Finding]:
    return [*check_text(listing), *check_price(listing), *check_quantities(listing)]
