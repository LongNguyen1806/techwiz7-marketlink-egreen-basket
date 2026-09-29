from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import CustomerProfile, CustomUser, FarmerProfile, FarmerStatus
from accounts.services.auth_service import account_locked_error
from catalog.models import Product, ProductMarket
from catalog.services.stock import get_held_quantities
from orders.exceptions import (
    CutoffPassedError,
    InsufficientStockError,
    OpenOrderLimitExceededError,
    ProductNotAvailableError,
    SlotNotAvailableError,
)
from orders.models import Order, OrderItem, OrderStatus
from orders.services.expiry import expire_overdue_orders
from orders.services.fsm import record_order_placed
from orders.services.pickup_service import resolve_pickup



def _lock_customer(customer) -> CustomUser:
    user = CustomUser.objects.select_for_update(of=("self",)).get(pk=customer.pk)
    user.customer_profile = CustomerProfile.objects.select_for_update(of=("self",)).get(user=user)
    if not user.is_active:
        raise account_locked_error(user)
    return user


def _share_lock_farmer_rows(farmer_ids) -> None:
    table = connection.ops.quote_name(FarmerProfile._meta.db_table)
    column = connection.ops.quote_name(FarmerProfile._meta.pk.column)
    placeholders = ", ".join(["%s"] * len(farmer_ids))
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {column} FROM {table} WHERE {column} IN ({placeholders}) ORDER BY {column} FOR SHARE", # nosec B608
            sorted(farmer_ids),
        )


def _lock_farmers(groups) -> dict:
    ids = [group["farmer_id"] for group in groups]
    _share_lock_farmer_rows(set(ids))
    approved = FarmerProfile.objects.select_related("user").filter(
        pk__in=ids, status=FarmerStatus.APPROVED, user__is_active=True
    )
    farmers = {farmer.pk: farmer for farmer in approved}
    missing = {
        f"groups.{index}.farmer_id": ["This farmer is not accepting orders"]
        for index, farmer_id in enumerate(ids)
        if farmer_id not in farmers
    }
    if missing:
        raise ProductNotAvailableError(errors=missing)
    return farmers


def expire_overdue_before_checkout(*, farmer_ids) -> None:
    """Lazy sweep (A-005) for the farmers in the cart, run by the view BEFORE the checkout transaction.

    Uses the Farmer branch's expire_overdue_orders(), which commits each T8 on its own; a PLACED order never
    took stock (D-029), so expiring it changes no stock.
    """
    for farmer_id in sorted(set(farmer_ids)):
        expire_overdue_orders(farmer_id=farmer_id)


def _check_placed_order_limit(customer, groups, now) -> None:
    """D-005 v1.5 guard 2: at most MAX_PLACED_ORDERS_PER_CUSTOMER orders waiting for farmer confirmation.

    Orders the farmer already accepted do not count, and there is no per-farmer limit. A PLACED order past
    its pickup start is already "expired" for the customer (A-005) even before a sweep, so it does not count.
    """
    limit = settings.MAX_PLACED_ORDERS_PER_CUSTOMER
    waiting = (
        Order.objects.filter(customer=customer, status=OrderStatus.PLACED)
        .exclude(pickup_start_at__lte=now)
        .count()
    )
    if waiting + len(groups) > limit:
        message = (
            f"You have {limit} orders waiting for farmer confirmation. "
            "Please wait for them to be confirmed before placing more."
        )
        raise OpenOrderLimitExceededError(message, errors={"non_field_errors": [message]})


def _resolve_windows(groups, farmers, now) -> list:
    windows = []
    for index, group in enumerate(groups):
        try:
            windows.append(resolve_pickup(
                farmer=farmers[group["farmer_id"]],
                pickup_slot_id=group["pickup_slot_id"],
                pickup_date=group["pickup_date"],
                now=now,
            ))
        except (SlotNotAvailableError, CutoffPassedError) as exc:
            raise type(exc)(errors={f"groups.{index}.pickup_slot_id": [str(exc.detail)]}) from exc
    return windows


def _is_published(product: Product) -> bool:
    return product.is_on_sale


def cap_message(product: Product) -> str:
    return f"You can order at most {product.max_per_order} {product.unit.lower()} of {product.name} per order"


def minimum_message(product: Product) -> str:
    return f"The minimum for {product.name} is {product.min_per_order} {product.unit.lower()} per order"


def _shortage_message(product: Product, available: int) -> str:
    if available == 0:
        return "Out of stock"
    return f"Only {available} {product.unit} left"


def _available_stock(products) -> dict[int, int]:
    held = get_held_quantities(product_ids=products.keys())
    return {pk: max(product.stock_quantity - held.get(pk, 0), 0) for pk, product in products.items()}


def _validate_products(groups, products) -> None:
    foreign, unpublished, over_cap, shortages, available = {}, {}, {}, {}, {}
    stock = _available_stock(products)
    for group_index, group in enumerate(groups):
        for item_index, item in enumerate(group["items"]):
            path = f"groups.{group_index}.items.{item_index}"
            product = products.get(item["product_id"])
            if product is None or product.farmer_id != group["farmer_id"]:
                foreign[f"{path}.product_id"] = ["This product does not belong to the selected farmer"]
            elif not _is_published(product):
                unpublished[f"{path}.product_id"] = ["This product is no longer available"]
            elif item["quantity"] < product.min_per_order:
                over_cap[f"{path}.quantity"] = [minimum_message(product)]
            elif product.max_per_order is not None and item["quantity"] > product.max_per_order:
                over_cap[f"{path}.quantity"] = [cap_message(product)]
            elif stock[product.id] < item["quantity"]:
                shortages[f"{path}.quantity"] = [_shortage_message(product, stock[product.id])]
                available[str(product.id)] = stock[product.id]
    if foreign:
        raise ValidationError(foreign)
    if unpublished:
        raise ProductNotAvailableError(errors=unpublished)
    if over_cap:
        raise ValidationError(over_cap)
    if shortages:
        raise InsufficientStockError(errors=shortages, data={"available": available})


def _validate_markets(groups, windows, products) -> None:
    stall_ids = {window.slot.farmer_market_id for window in windows}
    registered = set(
        ProductMarket.objects.filter(
            farmer_market_id__in=stall_ids, product_id__in=list(products)
        ).values_list("product_id", "farmer_market_id")
    )
    errors = {}
    for group_index, (group, window) in enumerate(zip(groups, windows)):
        for item_index, item in enumerate(group["items"]):
            if (item["product_id"], window.slot.farmer_market_id) not in registered:
                name = products[item["product_id"]].name
                errors[f"groups.{group_index}.items.{item_index}.product_id"] = [
                    f"{name} is not sold at {window.market.name}. Choose another pickup market or remove it."
                ]
    if errors:
        raise ProductNotAvailableError(errors=errors)


def _create_order(*, customer, farmer, group, window, products) -> Order:
    lines = [(products[item["product_id"]], item["quantity"]) for item in group["items"]]
    order = Order.objects.create(
        customer=customer,
        farmer=farmer,
        market=window.market,
        pickup_slot=window.slot,
        stall_label=window.stall_label,
        pickup_date=window.pickup_date,
        pickup_start_at=window.pickup_start_at,
        pickup_end_at=window.pickup_end_at,
        cutoff_at=window.cutoff_at,
        note=group.get("note") or None,
        total_amount=sum(product.price * quantity for product, quantity in lines),
    )
    OrderItem.objects.bulk_create([
        OrderItem(
            order=order, product=product, product_name=product.name, unit=product.unit,
            unit_price=product.price, quantity=quantity, line_total=product.price * quantity,
        )
        for product, quantity in lines
    ])
    record_order_placed(order=order, actor=customer)
    return order


def place_orders(*, customer, groups: list[dict], now=None) -> list[Order]:
    """CU-04 (v1.7 D-029): checks available stock but neither locks nor takes it; T2 does that."""
    now = now or timezone.now()
    with transaction.atomic():
        customer = _lock_customer(customer)
        farmers = _lock_farmers(groups)
        _check_placed_order_limit(customer, groups, now)
        windows = _resolve_windows(groups, farmers, now)

        cart_product_ids = {item["product_id"] for group in groups for item in group["items"]}
        products = Product.objects.in_bulk(cart_product_ids)
        _validate_products(groups, products)
        _validate_markets(groups, windows, products)
        return [
            _create_order(
                customer=customer, farmer=farmers[group["farmer_id"]], group=group, window=window, products=products
            )
            for group, window in zip(groups, windows)
        ]
