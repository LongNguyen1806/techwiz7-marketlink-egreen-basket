from datetime import datetime, time, timedelta

import pytest
from django.utils import timezone

from accounts.models import FarmerStatus
from catalog.models import Category, Product, ReviewStatus, Unit
from markets.models import FarmerMarket, Market, MarketOperatingDay, PickupSlot
from orders.models import Order, OrderItem, OrderStatus


@pytest.fixture
def category(db):
    return Category.objects.create(name="Vegetables", icon="carrot", display_order=1)


@pytest.fixture
def approved_farmer(farmer_user):
    profile = farmer_user.farmer_profile
    profile.status = FarmerStatus.APPROVED
    profile.save(update_fields=["status"])
    home = Market.objects.create(
        name="Home Market",
        address="9 Home Street",
        latitude="10.700000",
        longitude="106.600000",
        open_time=time(6, 0),
        close_time=time(12, 0),
    )
    FarmerMarket.objects.create(farmer=profile, market=home, stall_label="Home row, Stall 1")
    return profile


@pytest.fixture
def product(category, approved_farmer):
    # An established listing: written, reviewed, and on sale. A fresh Product() defaults to
    # PENDING, which is right for the model and wrong for a fixture the rest of the suite
    # treats as something a shopper can already see.
    return Product.objects.create(
        farmer=approved_farmer,
        category=category,
        name="Tomato",
        price="2.50",
        unit=Unit.KG,
        stock_quantity=10,
        review_status=ReviewStatus.APPROVED,
    )


@pytest.fixture
def seller_market(db, approved_farmer):
    market = Market.objects.create(
        name="Central Market",
        address="1 Market Street",
        latitude="10.762622",
        longitude="106.660172",
        open_time=time(6, 0),
        close_time=time(12, 0),
    )
    MarketOperatingDay.objects.create(market=market, day_of_week=1)
    farmer_market = FarmerMarket.objects.create(
        farmer=approved_farmer, market=market, stall_label="Row B, Stall 12"
    )
    PickupSlot.objects.create(
        farmer_market=farmer_market, day_of_week=1, start_time=time(7, 0), end_time=time(9, 0)
    )
    PickupSlot.objects.create(
        farmer_market=farmer_market,
        day_of_week=3,
        start_time=time(7, 0),
        end_time=time(9, 0),
        is_active=False,
    )
    return market


@pytest.fixture
def make_order_with_item(approved_farmer, customer_user, seller_market):
    # Pickup is tomorrow by default: a window at 08:00 today would already be in the past for
    # most of the working day, which silently changes what counts as an active order.
    def _make(*, product, quantity=2, status=OrderStatus.PLACED, days_ahead=1) -> Order:
        pickup_date = timezone.localdate() + timedelta(days=days_ahead)
        start = timezone.make_aware(datetime.combine(pickup_date, time(8, 0)))
        order = Order.objects.create(
            customer=customer_user,
            farmer=approved_farmer,
            market=seller_market,
            pickup_date=pickup_date,
            pickup_start_at=start,
            pickup_end_at=start + timedelta(hours=2),
            cutoff_at=start - timedelta(hours=12),
            status=status,
            total_amount="5.00",
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            unit_price=product.price,
            unit=product.unit,
            quantity=quantity,
            line_total=product.price,
        )
        return order

    return _make
