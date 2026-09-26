from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from rest_framework import serializers

from orders.models import Order, OrderItem, OrderStatus
from orders.services.pending_change import present_pending_change

# v1.8 OrderSummary.is_expiring_soon: a PLACED order at most this many hours before pickup starts.
EXPIRING_SOON_HOURS = 2


class CheckoutItemWriteSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=999)


class CheckoutGroupWriteSerializer(serializers.Serializer):
    farmer_id = serializers.IntegerField(min_value=1)
    pickup_slot_id = serializers.IntegerField(min_value=1)
    pickup_date = serializers.DateField()
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, allow_null=True)
    items = CheckoutItemWriteSerializer(many=True, allow_empty=False, max_length=50)

    def validate_items(self, items):
        product_ids = [item["product_id"] for item in items]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError("Each product can appear only once per farmer")
        return items


class CheckoutWriteSerializer(serializers.Serializer):
    groups = CheckoutGroupWriteSerializer(many=True, allow_empty=False, max_length=5)

    def validate_groups(self, groups):
        farmer_ids = [group["farmer_id"] for group in groups]
        if len(farmer_ids) != len(set(farmer_ids)):
            raise serializers.ValidationError("Each farmer can appear only once")
        return groups


class OrderSummaryReadSerializer(serializers.ModelSerializer):
    is_overdue = serializers.SerializerMethodField()
    is_expiring_soon = serializers.SerializerMethodField()
    has_pending_change = serializers.SerializerMethodField()
    customer = serializers.SerializerMethodField()
    farmer = serializers.SerializerMethodField()
    market = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()
    # Money is USD DECIMAL(10,2); DRF renders it as a string such as "12.50" to avoid float rounding.
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        model = Order
        fields = [
            "id", "status", "is_overdue", "is_expiring_soon", "has_pending_change", "version", "customer", "farmer", "market",
            "stall_label", "pickup_date", "pickup_start_at", "pickup_end_at", "cutoff_at", "item_count",
            "total_amount", "created_at",
        ]

    def get_is_overdue(self, order) -> bool:
        return order.status == OrderStatus.PLACED and timezone.now() >= order.pickup_start_at

    def get_is_expiring_soon(self, order) -> bool:
        now = timezone.now()
        return (
            order.status == OrderStatus.PLACED
            and order.pickup_start_at - timedelta(hours=EXPIRING_SOON_HOURS) <= now < order.pickup_start_at
        )

    def get_has_pending_change(self, order) -> bool:
        # D-030: an ACCEPTED order with a change request waiting for the farmer.
        return order.pending_change is not None

    def get_customer(self, order) -> dict:
        profile = order.customer.customer_profile
        return {"id": order.customer_id, "full_name": profile.full_name, "phone": profile.phone}

    def get_farmer(self, order) -> dict:
        return {"id": order.farmer_id, "stall_name": order.farmer.stall_name, "phone": order.farmer.phone}

    def get_market(self, order) -> dict:
        market = order.market
        return {
            "id": market.id, "name": market.name, "address": market.address,
            "latitude": float(market.latitude), "longitude": float(market.longitude),
        }

    def get_item_count(self, order) -> int:
        annotated = getattr(order, "item_count", None)
        return annotated if annotated is not None else order.items.count()


FINISHED_STATUSES = (
    OrderStatus.COMPLETED, OrderStatus.CANCELLED, OrderStatus.DECLINED, OrderStatus.NO_SHOW, OrderStatus.EXPIRED,
)


class CustomerOrderListQuerySerializer(serializers.Serializer):
    """CU-05 query string."""

    tab = serializers.ChoiceField(choices=["open", "history"], required=False)
    status = serializers.CharField(required=False)  # comma-separated, e.g. "PLACED,ACCEPTED"
    farmer_id = serializers.IntegerField(min_value=1, required=False)
    pickup_from = serializers.DateField(required=False)
    pickup_to = serializers.DateField(required=False)
    ordering = serializers.ChoiceField(choices=["pickup_start_at", "-created_at"], required=False)

    def validate_status(self, value: str) -> list[str]:
        statuses = [part.strip() for part in value.split(",") if part.strip()]
        unknown = [status for status in statuses if status not in OrderStatus.values]
        if unknown or not statuses:
            raise serializers.ValidationError(f"Unknown status: {', '.join(unknown) or value}")
        return statuses


# Pass 4A order_status_history.change_reason: system codes are translated when returned (Pass 4B §3.4).
SYSTEM_REASON_TEXT = {
    "SYSTEM_EXPIRED": "The order expired because the farmer did not confirm it before pickup.",
    "FARMER_SUSPENDED_BY_ADMIN": "The farmer's stall is no longer accepting orders.",
    "CUSTOMER_LOCKED_BY_ADMIN": "The order was closed because the account was locked.",
    "MARKET_CLOSED_BY_ADMIN": "The order was cancelled because the market has closed.",
}


class CustomerStatusHistoryReadSerializer(serializers.Serializer):
    from_status = serializers.CharField(allow_null=True)
    to_status = serializers.CharField()
    transition = serializers.CharField(allow_null=True)
    actor_role = serializers.CharField()
    actor_name = serializers.SerializerMethodField()
    change_reason = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()

    def get_actor_name(self, entry) -> str | None:
        # Admin and system steps stay anonymous (D-033); customers see who acted by stall or own name.
        actor = entry.actor
        if actor is None or entry.actor_role not in ("CUSTOMER", "FARMER"):
            return None
        profile = getattr(actor, "farmer_profile", None) if entry.actor_role == "FARMER" else None
        if profile is not None:
            return profile.stall_name
        profile = getattr(actor, "customer_profile", None)
        return profile.full_name if profile is not None else None

    def get_change_reason(self, entry) -> str | None:
        return SYSTEM_REASON_TEXT.get(entry.change_reason, entry.change_reason)


class CustomerOrderItemReadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    unit = serializers.CharField()
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField()
    line_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    product_image = serializers.SerializerMethodField()

    def get_product_image(self, item) -> str | None:
        image = item.product.image
        return image.url if image else None


def _has_review(obj, related_name: str) -> bool:
    # Reverse one-to-one (Order.farmer_review, OrderItem.product_review) raises when there is no review.
    try:
        getattr(obj, related_name)
    except ObjectDoesNotExist:
        return False
    return True


def customer_allowed_actions(order, *, review_state: dict | None, now=None) -> list[str]:
    """Pass 4B §3.4 / §5.3: what the customer may do now; the frontend only renders these buttons."""
    now = now or timezone.now()
    before_cutoff = now < order.cutoff_at
    if order.status == OrderStatus.PLACED:
        return ["MODIFY", "CANCEL"] if before_cutoff else []
    if order.status == OrderStatus.ACCEPTED:
        return ["REQUEST_CHANGE", "CANCEL"] if before_cutoff else []
    actions = []
    if review_state and (not review_state["farmer_reviewed"] or review_state["items_pending_review"]):
        actions.append("REVIEW")
    if order.status in FINISHED_STATUSES:
        actions.append("REORDER")
    return actions


class CustomerOrderDetailReadSerializer(OrderSummaryReadSerializer):
    """Pass 4B §3.4 OrderDetail, as the customer sees it (no customer email)."""

    pickup_slot_id = serializers.IntegerField(allow_null=True)
    note = serializers.CharField(allow_null=True)
    items = CustomerOrderItemReadSerializer(many=True)
    status_history = CustomerStatusHistoryReadSerializer(many=True)
    pending_change = serializers.SerializerMethodField()
    allowed_actions = serializers.SerializerMethodField()
    review_state = serializers.SerializerMethodField()

    class Meta(OrderSummaryReadSerializer.Meta):
        fields = OrderSummaryReadSerializer.Meta.fields + [
            "pickup_slot_id", "note", "items", "status_history", "pending_change", "allowed_actions", "review_state",
        ]

    def get_pending_change(self, order) -> dict | None:
        # v1.8 shared presenter (Farmer branch): prices the customer saw when sending the request.
        return present_pending_change(order)

    def get_review_state(self, order) -> dict | None:
        if order.status != OrderStatus.COMPLETED:
            return None
        return {
            "farmer_reviewed": _has_review(order, "farmer_review"),
            "items_pending_review": [item.id for item in order.items.all() if not _has_review(item, "product_review")],
        }

    def get_allowed_actions(self, order) -> list[str]:
        return customer_allowed_actions(order, review_state=self.get_review_state(order))


class CancelOrderWriteSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True)


class CustomerOrderItemModifySerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)


class CustomerOrderModifySerializer(serializers.Serializer):
    pickup_slot_id = serializers.IntegerField(required=False, allow_null=True)
    pickup_date = serializers.DateField(required=False, allow_null=True)
    note = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=300
    )
    items = CustomerOrderItemModifySerializer(many=True, required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        slot_id = attrs.get("pickup_slot_id")
        p_date = attrs.get("pickup_date")

        if (slot_id is None and p_date is not None) or (slot_id is not None and p_date is None):
            raise serializers.ValidationError(
                "Both pickup_slot_id and pickup_date are required to reschedule pickup timing."
            )

        items = attrs.get("items")
        if items is not None:
            if len(items) == 0:
                raise serializers.ValidationError(
                    {
                        "items": "An order must contain at least one item. To cancel the order, please use cancel order."
                    }
                )
            pids = [item["product_id"] for item in items]
            if len(pids) != len(set(pids)):
                raise serializers.ValidationError(
                    {"items": "Duplicate products are not allowed in the items list."}
                )

        if not attrs:
            raise serializers.ValidationError("At least one field to update must be provided.")

        return attrs


class CustomerOrderItemDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product_id",
            "product_name",
            "unit",
            "unit_price",
            "quantity",
            "line_total",
        ]


class CustomerOrderDetailSerializer(serializers.ModelSerializer):
    market_name = serializers.CharField(source="market.name", read_only=True)
    farmer_stall_name = serializers.CharField(source="farmer.stall_name", read_only=True)
    items = CustomerOrderItemDetailSerializer(many=True, read_only=True)
    allowed_actions = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "status",
            "version",
            "market_name",
            "farmer_stall_name",
            "stall_label",
            "pickup_date",
            "pickup_start_at",
            "pickup_end_at",
            "cutoff_at",
            "note",
            "total_amount",
            "items",
            "allowed_actions",
            "created_at",
            "updated_at",
        ]

    def get_allowed_actions(self, obj: Order) -> list[str]:
        actions: list[str] = []
        now = timezone.now()
        if obj.status in (OrderStatus.PLACED, OrderStatus.ACCEPTED) and now < obj.cutoff_at:
            actions.append("MODIFY")
            actions.append("CANCEL")
        return actions
