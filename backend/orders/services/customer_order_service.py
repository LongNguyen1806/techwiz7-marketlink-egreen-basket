from marketlink_core.exceptions import ResourceNotFoundError
from orders.models import ActorRole, Order, OrderStatus
from orders.services.fsm import transition_order
from orders.services.modify import modify_order
from orders.services.pickup_service import check_customer_pickup_date


def _own_order(*, customer, order_id: int) -> Order:
    # Someone else's order is "not found" (Pass 4B §6), before the shared services could answer 403.
    order = Order.objects.select_related("farmer").filter(pk=order_id, customer=customer).first()
    if order is None:
        raise ResourceNotFoundError()
    return order


def cancel_customer_order(*, customer, order_id: int, expected_version: int, reason: str | None = None) -> Order:
    """CU-08: T5 (PLACED) or T6 (ACCEPTED) through the Farmer branch's FSM, which checks cutoff and stock."""
    _own_order(customer=customer, order_id=order_id)
    return transition_order(
        order_id=order_id,
        to_status=OrderStatus.CANCELLED,
        actor=customer,
        actor_role=ActorRole.CUSTOMER,
        expected_version=expected_version,
        reason=reason,
    )


def modify_customer_order(*, customer, order_id: int, expected_version: int, data: dict) -> Order:
    """CU-07 (D-030) through the Farmer branch's modify_order(): PLACED is edited in place, ACCEPTED gets a
    change request in orders.pending_change."""
    order = _own_order(customer=customer, order_id=order_id)
    if data.get("pickup_date") is not None:
        check_customer_pickup_date(farmer=order.farmer, pickup_date=data["pickup_date"])
    return modify_order(
        order_id=order_id,
        actor=customer,
        expected_version=expected_version,
        items_data=data.get("items"),
        pickup_date=data.get("pickup_date"),
        pickup_slot_id=data.get("pickup_slot_id"),
        note=data.get("note"),
    )
