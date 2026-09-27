import pytest

from notifications.models import Notification
from notifications.services import notify
from orders.services.notification_context import build_order_context
from tests_support.factories import make_customer, make_farmer, make_order, make_product


@pytest.mark.django_db
class TestNotify:
    def test_order_placed_goes_to_farmer_inbox(self):
        product = make_product(farmer=make_farmer())
        order = make_order(customer=make_customer(), product=product)

        note = notify(recipient=product.farmer.user, event_type="ORDER_PLACED", context=build_order_context(order))

        stored = Notification.objects.get(pk=note.pk)
        assert (stored.recipient_id, stored.type, stored.is_read) == (product.farmer.user_id, "ORDER_PLACED", False)
        assert stored.title == f"New order #{order.pk}"
        assert stored.target_url == f"/farmer/orders/{order.pk}"

    def test_order_expired_goes_to_customer_inbox(self):
        customer = make_customer()
        order = make_order(customer=customer, product=make_product(farmer=make_farmer()))

        note = notify(recipient=customer, event_type="ORDER_EXPIRED", context=build_order_context(order))

        assert (note.recipient_id, note.type, note.target_url) == (customer.id, "ORDER_EXPIRED", f"/customer/orders/{order.pk}")
