import itertools
from datetime import time, timedelta
from decimal import Decimal

from django.utils import timezone

from accounts.models import CustomerProfile, CustomUser, FarmerProfile, FarmerStatus, Role
from catalog.models import Category, Product, ProductMarket, ReviewStatus, Unit
from markets.models import FarmerMarket, Market, MarketOperatingDay, PickupSlot
from orders.models import Order, OrderItem, OrderStatus

PASSWORD = "Mango2026x"
_sequence = itertools.count(1)


def _next() -> int:
    return next(_sequence)


def make_customer(*, is_active: bool = True) -> CustomUser:
    n = _next()
    user = CustomUser.objects.create_user(
        email=f"customer{n}@example.com",
        password=PASSWORD,
        role=Role.objects.get(code="CUSTOMER"),
        is_active=is_active,
    )
    CustomerProfile.objects.create(
        user=user, full_name=f"Customer {n}", phone=f"091{n:07d}", address="12 Market Street"
    )
    return user


def make_farmer(*, status: str = FarmerStatus.APPROVED, cutoff_hours: int = 12, operating_days=range(1, 8)) -> FarmerProfile:
    n = _next()
    user = CustomUser.objects.create_user(
        email=f"farmer{n}@example.com", password=PASSWORD, role=Role.objects.get(code="FARMER")
    )
    return FarmerProfile.objects.create(
        user=user,
        stall_name=f"Stall {n}",
        contact_person=f"Farmer {n}",
        phone=f"098{n:07d}",
        address="5 Farm Road",
        status=status,
        order_cutoff_hours=cutoff_hours,
        operating_days=list(operating_days),
    )


def make_market(*, days=range(1, 8), is_active: bool = True) -> Market:
    n = _next()
    market = Market.objects.create(
        name=f"Market {n}",
        address=f"{n} Market Road",
        latitude=Decimal("10.772345"),
        longitude=Decimal("106.698765"),
        open_time=time(5, 0),
        close_time=time(20, 0),
        is_active=is_active,
    )
    MarketOperatingDay.objects.bulk_create(
        [MarketOperatingDay(market=market, day_of_week=day) for day in days]
    )
    return market


def sell_at_every_stall(farmer) -> None:
    """Test convenience: register each of the farmer's products at each of the farmer's stalls."""
    ProductMarket.objects.bulk_create(
        [
            ProductMarket(product_id=product_id, farmer_market_id=stall_id)
            for product_id in Product.objects.filter(farmer=farmer).values_list("pk", flat=True)
            for stall_id in FarmerMarket.objects.filter(farmer=farmer).values_list("pk", flat=True)
        ],
        ignore_conflicts=True,
    )


def make_slot(*, farmer, market, day_of_week: int, start=time(8, 0), end=time(10, 0), is_active=True) -> PickupSlot:
    farmer_market, _ = FarmerMarket.objects.get_or_create(
        farmer=farmer, market=market, defaults={"stall_label": "Row B, stall 12"}
    )
    sell_at_every_stall(farmer)
    return PickupSlot.objects.create(
        farmer_market=farmer_market, day_of_week=day_of_week, start_time=start, end_time=end, is_active=is_active
    )


def make_product(*, farmer, stock: int = 10, price: str = "2.50", **overrides) -> Product:
    category, _ = Category.objects.get_or_create(name="Vegetables")
    fields = {
        "farmer": farmer,
        "category": category,
        "name": f"Product {_next()}",
        "price": Decimal(price),
        "unit": Unit.KG,
        "stock_quantity": stock,
        "review_status": ReviewStatus.APPROVED,
    }
    fields.update(overrides)
    product = Product.objects.create(**fields)
    sell_at_every_stall(farmer)
    return product


def make_order(*, customer, product, quantity: int = 2, status: str = OrderStatus.PLACED, pickup_start_at=None, market=None) -> Order:
    start = pickup_start_at or timezone.now() + timedelta(days=3)
    order = Order.objects.create(
        customer=customer,
        farmer=product.farmer,
        market=market or make_market(),
        stall_label="Row B, stall 12",
        pickup_date=timezone.localdate(start),
        pickup_start_at=start,
        pickup_end_at=start + timedelta(hours=2),
        cutoff_at=start - timedelta(hours=12),
        status=status,
        total_amount=product.price * quantity,
    )
    OrderItem.objects.create(
        order=order,
        product=product,
        product_name=product.name,
        unit=product.unit,
        unit_price=product.price,
        quantity=quantity,
        line_total=product.price * quantity,
    )
    return order
