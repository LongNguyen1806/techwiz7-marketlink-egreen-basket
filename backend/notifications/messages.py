from dataclasses import dataclass

from notifications.models import NotificationType

TITLE_MAX_LENGTH = 150
MESSAGE_MAX_LENGTH = 500


@dataclass(frozen=True)
class NotificationSpec:
    title: str
    message: str
    target_url: str | None
    required: tuple[str, ...]
    email_template: str | None = None


NOTIFICATION_SPECS: dict[str, NotificationSpec] = {
    NotificationType.ORDER_ACCEPTED: NotificationSpec(
        title="Order #{order_id} accepted",
        message="{farmer_name} accepted your order. Pickup: {pickup_label} at {market_name}.",
        target_url="/customer/orders/{order_id}",
        required=("order_id", "farmer_name", "pickup_label", "market_name"),
        email_template="order_accepted",
    ),
    NotificationType.ORDER_READY: NotificationSpec(
        title="Order #{order_id} is ready for pickup",
        message=(
            "{farmer_name} has packed your order. Pick it up {pickup_label} "
            "at {market_name} ({stall_label})."
        ),
        target_url="/customer/orders/{order_id}",
        required=("order_id", "farmer_name", "pickup_label", "market_name", "stall_label"),
        email_template="order_ready",
    ),
    NotificationType.ORDER_DECLINED: NotificationSpec(
        title="Order #{order_id} was declined",
        message="{farmer_name} declined your order. Reason: {reason}",
        target_url="/customer/orders/{order_id}",
        required=("order_id", "farmer_name", "reason"),
        email_template="order_declined",
    ),
    NotificationType.ORDER_EXPIRED: NotificationSpec(
        title="Order #{order_id} expired",
        message=(
            "{farmer_name} did not confirm your order before the pickup time, so it has "
            "expired and the reserved items were released."
        ),
        target_url="/customer/orders/{order_id}",
        required=("order_id", "farmer_name"),
        email_template="order_expired",
    ),
    NotificationType.ORDER_CHANGE_APPROVED: NotificationSpec(
        title="Change request approved for order #{order_id}",
        message="{farmer_name} approved your change request for order #{order_id}.",
        target_url="/customer/orders/{order_id}",
        required=("order_id", "farmer_name"),
    ),
    NotificationType.ORDER_CHANGE_REJECTED: NotificationSpec(
        title="Change request rejected for order #{order_id}",
        message="{farmer_name} rejected your change request for order #{order_id}. Reason: {reason}",
        target_url="/customer/orders/{order_id}",
        required=("order_id", "farmer_name", "reason"),
    ),
    NotificationType.RESTOCK: NotificationSpec(
        title="{product_name} is back in stock",
        message="{farmer_name} restocked {product_name}, one of your favorites.",
        target_url="/products/{product_id}",
        required=("product_id", "product_name", "farmer_name"),
    ),
    NotificationType.ORDER_PLACED: NotificationSpec(
        title="New order #{order_id}",
        message="{customer_name} placed an order for pickup {pickup_label} at {market_name}.",
        target_url="/farmer/orders/{order_id}",
        required=("order_id", "customer_name", "pickup_label", "market_name"),
    ),
    NotificationType.ORDER_MODIFIED: NotificationSpec(
        title="Order #{order_id} was modified",
        message="{customer_name} changed the order: {change_summary}",
        target_url="/farmer/orders/{order_id}",
        required=("order_id", "customer_name", "change_summary"),
    ),
    NotificationType.ORDER_CANCELLED: NotificationSpec(
        title="Order #{order_id} was cancelled",
        message="{customer_name} cancelled the order. Reason: {reason}",
        target_url="/farmer/orders/{order_id}",
        required=("order_id", "customer_name", "reason"),
        email_template="order_cancelled_by_customer",
    ),
    NotificationType.ORDER_CANCELLED_CUSTOMER_LOCKED: NotificationSpec(
        title="Order #{order_id} was cancelled",
        message=(
            "The customer's account was locked by an administrator, so this order was "
            "cancelled and the items have been returned to your online stock."
        ),
        target_url="/farmer/orders/{order_id}",
        required=("order_id",),
        email_template="order_cancelled_customer_locked",
    ),
    NotificationType.ACCOUNT_STATUS_CHANGED: NotificationSpec(
        title="Your seller account is now {status_label}",
        message="An administrator changed your account status to {status_label}. {reason}",
        target_url="/farmer",
        required=("status_label",),
    ),
    NotificationType.MARKET_CLOSED: NotificationSpec(
        title="{market_name} has closed",
        message=(
            "{market_name} is no longer running, so {order_count} of your orders there were "
            # stall_note is optional and renders empty for shoppers. It carries the stall's
            # suspension, so closing a market sends one message rather than two about the
            # same event.
            "cancelled. Reason: {reason} {stall_note}"
        ),
        # Both sides read this one, so the link goes to the list each role actually has.
        target_url="{target_url}",
        required=("market_name", "order_count", "reason", "target_url"),
        # Closing a market is the kind of thing someone needs to hear about even if they are
        # not looking at the app, so this one also goes out by email.
        email_template="market_closed",
    ),
    NotificationType.PRODUCT_BLOCKED: NotificationSpec(
        title="{product_name} was taken down",
        message=(
            "An administrator removed {product_name} from the marketplace and cancelled "
            "{order_count} open orders for it. Reason: {reason}"
        ),
        target_url="/farmer/products",
        required=("product_name", "order_count", "reason"),
        # In-app only. D-010 names the six events that also go out by email and this is not
        # one of them; the stall sees it the next time they open the app.
    ),
    NotificationType.PRODUCT_APPROVED: NotificationSpec(
        title="{product_name} is on sale",
        message="An administrator approved {product_name}. Shoppers can see it now.",
        target_url="/farmer/products",
        required=("product_name",),
    ),
    NotificationType.PRODUCT_REJECTED: NotificationSpec(
        title="{product_name} was not approved",
        message=(
            "An administrator did not approve {product_name}, so it is not on sale. "
            "Reason: {reason}"
        ),
        target_url="/farmer/products",
        required=("product_name", "reason"),
    ),
    NotificationType.MARKET_SCHEDULE_CHANGED: NotificationSpec(
        title="{market_name} changed its schedule",
        message=(
            "{slot_count} of your pickup slots at {market_name} were turned off because they "
            "fall outside the new market schedule. Please review them."
        ),
        target_url="/farmer/markets",
        required=("market_name", "slot_count"),
    ),
}

EMAIL_EVENT_TYPES = frozenset(
    event for event, spec in NOTIFICATION_SPECS.items() if spec.email_template
)


class _OptionalKeys(dict):
    def __missing__(self, key: str) -> str:
        return ""


def render_notification(event_type: str, context: dict) -> tuple[str, str, str | None]:
    try:
        spec = NOTIFICATION_SPECS[event_type]
    except KeyError as exc:
        raise ValueError(f"Unknown notification event type: {event_type}") from exc
    missing = [key for key in spec.required if context.get(key) in (None, "")]
    if missing:
        raise ValueError(f"Notification {event_type} is missing context keys: {', '.join(missing)}")
    values = _OptionalKeys(context)
    title = spec.title.format_map(values)[:TITLE_MAX_LENGTH]
    message = spec.message.format_map(values).strip()[:MESSAGE_MAX_LENGTH]
    target_url = spec.target_url.format_map(values) if spec.target_url else None
    return title, message, target_url
