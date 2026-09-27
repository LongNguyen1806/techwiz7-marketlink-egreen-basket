from datetime import timedelta
from typing import Any

from django.utils import timezone
from rest_framework import serializers

from orders.models import ActorRole, Order, OrderItem, OrderStatus, OrderStatusHistory
from orders.services.fsm import SYSTEM_REASON_TEXT
from orders.services.pending_change import present_pending_change

# W4.1: a PLACED order this close to pickup_start_at is highlighted before it auto-expires.
EXPIRING_SOON_HOURS = 2


def _image_url(image: Any, request: Any) -> str | None:
    if not image:
        return None
    return request.build_absolute_uri(image.url) if request is not None else image.url


class FarmerOrderItemSerializer(serializers.ModelSerializer):
    """OrderItem (Pass 4B §3.4)."""

    product_image = serializers.SerializerMethodField()

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
            "product_image",
        ]

    def get_product_image(self, obj: OrderItem) -> str | None:
        return _image_url(obj.product.image, self.context.get("request"))


class FarmerOrderStatusHistorySerializer(serializers.ModelSerializer):
    """StatusHistory (Pass 4B §3.4): system codes are translated, actor shown by name."""

    actor_name = serializers.SerializerMethodField()
    change_reason = serializers.SerializerMethodField()

    class Meta:
        model = OrderStatusHistory
        fields = [
            "from_status",
            "to_status",
            "transition",
            "actor_role",
            "actor_name",
            "change_reason",
            "created_at",
        ]

    def get_actor_name(self, obj: OrderStatusHistory) -> str | None:
        if obj.actor_role == ActorRole.SYSTEM or obj.actor is None:
            return None
        if obj.actor_role == ActorRole.ADMIN:
            return "Administrator"
        if obj.actor_role == ActorRole.FARMER:
            profile = getattr(obj.actor, "farmer_profile", None)
            return profile.stall_name if profile else None
        profile = getattr(obj.actor, "customer_profile", None)
        return profile.full_name if profile else None

    def get_change_reason(self, obj: OrderStatusHistory) -> str | None:
        return SYSTEM_REASON_TEXT.get(obj.change_reason, obj.change_reason)


class FarmerOrderSummarySerializer(serializers.ModelSerializer):
    """OrderSummary (Pass 4B §3.4) + farmer-only stock_warning / is_expiring_soon."""

    is_overdue = serializers.SerializerMethodField()
    is_expiring_soon = serializers.SerializerMethodField()
    has_pending_change = serializers.SerializerMethodField()
    customer = serializers.SerializerMethodField()
    farmer = serializers.SerializerMethodField()
    market = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()
    stock_warning = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "status",
            "is_overdue",
            "is_expiring_soon",
            "has_pending_change",
            "version",
            "customer",
            "farmer",
            "market",
            "stall_label",
            "pickup_date",
            "pickup_start_at",
            "pickup_end_at",
            "cutoff_at",
            "item_count",
            "total_amount",
            "stock_warning",
            "created_at",
        ]

    def get_is_overdue(self, obj: Order) -> bool:
        # PLACED past pickup_start_at but not swept yet (D-009).
        return obj.status == OrderStatus.PLACED and timezone.now() >= obj.pickup_start_at

    def get_is_expiring_soon(self, obj: Order) -> bool:
        now = timezone.now()
        return (
            obj.status == OrderStatus.PLACED
            and obj.pickup_start_at - timedelta(hours=EXPIRING_SOON_HOURS) <= now < obj.pickup_start_at
        )

    def get_has_pending_change(self, obj: Order) -> bool:
        return obj.pending_change is not None

    def get_customer(self, obj: Order) -> dict[str, Any]:
        profile = getattr(obj.customer, "customer_profile", None)
        return {
            "id": obj.customer_id,
            "full_name": profile.full_name if profile else obj.customer.email,
            "phone": profile.phone if profile else "",
        }

    def get_farmer(self, obj: Order) -> dict[str, Any]:
        return {"id": obj.farmer_id, "stall_name": obj.farmer.stall_name, "phone": obj.farmer.phone}

    def get_market(self, obj: Order) -> dict[str, Any]:
        market = obj.market
        return {
            "id": market.id,
            "name": market.name,
            "address": market.address,
            "latitude": float(market.latitude),
            "longitude": float(market.longitude),
        }

    def get_item_count(self, obj: Order) -> int:
        return len(obj.items.all())

    def get_stock_warning(self, obj: Order) -> bool:
        # F-02 (D-029): current stock cannot cover an item of this PLACED order.
        if obj.status != OrderStatus.PLACED:
            return False
        return any(item.product.stock_quantity < item.quantity for item in obj.items.all())


class FarmerOrderDetailSerializer(FarmerOrderSummarySerializer):
    """OrderDetail (Pass 4B §3.4) = OrderSummary + detail fields."""

    items = FarmerOrderItemSerializer(many=True, read_only=True)
    status_history = FarmerOrderStatusHistorySerializer(many=True, read_only=True)
    pending_change = serializers.SerializerMethodField()
    allowed_actions = serializers.SerializerMethodField()

    class Meta(FarmerOrderSummarySerializer.Meta):
        fields = FarmerOrderSummarySerializer.Meta.fields + [
            "pickup_slot_id",
            "note",
            "items",
            "status_history",
            "pending_change",
            "allowed_actions",
        ]

    def get_customer(self, obj: Order) -> dict[str, Any]:
        return {**super().get_customer(obj), "email": obj.customer.email}

    def get_pending_change(self, obj: Order) -> dict[str, Any] | None:
        # Pass 4B §3.4 shape, not the raw JSON column (D-030).
        return present_pending_change(obj)

    def get_allowed_actions(self, obj: Order) -> list[str]:
        actions: list[str] = []
        now = timezone.now()
        if obj.status == OrderStatus.PLACED:
            if now < obj.pickup_start_at:
                actions.extend(["ACCEPT", "DECLINE"])
                # FA-36 needs at least one item left after removal.
                if len(obj.items.all()) > 1:
                    actions.append("MARK_ITEM_SOLD_OUT")
        elif obj.status == OrderStatus.ACCEPTED:
            if obj.pending_change:
                if now < obj.pickup_start_at:
                    actions.extend(["APPROVE_CHANGE", "REJECT_CHANGE", "DECLINE"])
            else:
                if now >= obj.cutoff_at:
                    actions.append("READY")
                if now < obj.pickup_start_at:
                    actions.append("DECLINE")
                if now >= obj.pickup_end_at:
                    actions.append("NO_SHOW")
        elif obj.status == OrderStatus.READY_FOR_PICKUP:
            actions.append("COMPLETE")
            if now >= obj.pickup_end_at:
                actions.append("NO_SHOW")
        return actions


class DeclineOrderSerializer(serializers.Serializer):
    """FA-24 body. No defaults: an absent field means "not declared" (T4 requires one)."""

    reason = serializers.CharField(min_length=5, max_length=500)
    mark_sold_out = serializers.BooleanField(required=False)
    mark_sold_out_product_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if "mark_sold_out" in attrs and "mark_sold_out_product_ids" in attrs:
            raise serializers.ValidationError(
                {"mark_sold_out": ["Send either mark_sold_out or mark_sold_out_product_ids, not both."]}
            )
        return attrs


class RejectChangeRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True)


class PrepListItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    unit = serializers.CharField()
    total_quantity = serializers.IntegerField()
    order_count = serializers.IntegerField()
