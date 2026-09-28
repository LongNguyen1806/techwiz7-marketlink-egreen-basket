from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from notifications.models import Notification
from orders.services.expiry import expire_overdue_orders
from tests_support.factories import make_customer, make_farmer, make_order, make_product


def _past():
    return timezone.now() - timedelta(hours=1)


@pytest.fixture
def product(db):
    return make_product(farmer=make_farmer(), stock=5)


@pytest.mark.django_db
class TestExpireOverdueOrders:
    def test_expires_overdue_placed_order(self, product):
        customer = make_customer()
        order = make_order(customer=customer, product=product, quantity=2, pickup_start_at=_past())

        count = expire_overdue_orders(farmer_id=product.farmer_id)

        order.refresh_from_db()
        product.refresh_from_db()
        assert count == 1
        assert (order.status, order.version) == ("EXPIRED", 2)
        assert product.stock_quantity == 5
        history = order.status_history.get()
        assert (history.from_status, history.to_status, history.transition) == ("PLACED", "EXPIRED", "T8")
        assert (history.actor_id, history.actor_role, history.change_reason) == (None, "SYSTEM", "SYSTEM_EXPIRED")
        assert Notification.objects.get(recipient=customer).type == "ORDER_EXPIRED"

    def test_leaves_future_and_non_placed_orders_alone(self, product):
        future = make_order(customer=make_customer(), product=product)
        accepted = make_order(customer=make_customer(), product=product, status="ACCEPTED", pickup_start_at=_past())

        assert expire_overdue_orders(farmer_id=product.farmer_id) == 0
        future.refresh_from_db()
        accepted.refresh_from_db()
        assert (future.status, accepted.status) == ("PLACED", "ACCEPTED")

    def test_only_touches_the_given_farmer(self, product):
        other = make_order(customer=make_customer(), product=make_product(farmer=make_farmer()), pickup_start_at=_past())

        assert expire_overdue_orders(farmer_id=product.farmer_id) == 0
        other.refresh_from_db()
        assert other.status == "PLACED"

    def test_returned_stock_does_not_send_restock_alerts(self, product):
        make_order(customer=make_customer(), product=product, pickup_start_at=_past())

        expire_overdue_orders()

        assert not Notification.objects.filter(type="RESTOCK").exists()

    def test_management_command_reports_count(self, product):
        make_order(customer=make_customer(), product=product, pickup_start_at=_past())
        out = StringIO()

        call_command("expire_orders", stdout=out)

        assert "Expired 1 order(s)" in out.getvalue()

