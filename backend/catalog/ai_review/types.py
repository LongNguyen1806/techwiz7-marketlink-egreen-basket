"""Shapes shared by the rule layer, the model layer and the service.

Both layers read a ``ListingInput`` rather than a ``Product`` so the same checks run on a saved
listing, on a farmer's form before it is saved (precheck), and on the evaluation cases.
"""

from dataclasses import asdict, dataclass, field
from decimal import Decimal

from catalog.models import AIVerdict


class Severity:
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


SEVERITY_WEIGHT = {Severity.LOW: 10, Severity.MEDIUM: 30, Severity.HIGH: 60}


@dataclass(frozen=True)
class ListingInput:
    name: str
    description: str
    category_id: int | None
    category_name: str
    unit: str
    price: Decimal
    stock_quantity: int
    min_per_order: int = 1
    max_per_order: int | None = None
    product_id: int | None = None
    image_bytes: bytes | None = field(default=None, repr=False)
    image_mime: str | None = None


@dataclass(frozen=True)
class Finding:
    source: str
    check: str
    severity: str
    message: str

    def as_dict(self) -> dict:
        return asdict(self)


def risk_score(findings: list[Finding]) -> int:
    return min(100, sum(SEVERITY_WEIGHT.get(finding.severity, 0) for finding in findings))


def verdict_for(findings: list[Finding]) -> str:
    """HIGH anywhere -> likely violation; any MEDIUM, or several LOWs -> a closer look."""
    severities = {finding.severity for finding in findings}
    if Severity.HIGH in severities:
        return AIVerdict.LIKELY_VIOLATION
    if Severity.MEDIUM in severities or risk_score(findings) >= 30:
        return AIVerdict.NEEDS_REVIEW
    return AIVerdict.PASS
