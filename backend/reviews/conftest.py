from datetime import datetime, time, timedelta

import pytest
from django.utils import timezone

from accounts.models import FarmerStatus
from catalog.models import Category, Product, ReviewStatus, Unit
from markets.models import Market
from orders.models import Order, OrderItem, OrderStatus
from reviews.models import FarmerReview, ProductReview


@pytest.fixture
def approved_farmer(farmer_user):
    profile = farmer_user.farmer_profile
    profile.status = FarmerStatus.APPROVED
    profile.save(update_fields=["status"])
    return profile


@pytest.fixture
def market(db):
    return Market.objects.create(
        name="Central Market",
        address="1 Market Street",
        latitude="10.762622",
        longitude="106.660172",
        open_time=time(6, 0),
        close_time=time(12, 0),
    )


@pytest.fixture
def product(db, approved_farmer):
    # Icons are unique per category now, so a fixture cannot leave it to the default.
    category = Category.objects.create(name="Vegetables", icon="carrot", display_order=1)
    return Product.objects.create(
        farmer=approved_farmer,
        category=category,
        name="Tomato",
        price="2.50",
        unit=Unit.KG,
        stock_quantity=10,
        # A listing shoppers can already see, which is what these tests are about.
        review_status=ReviewStatus.APPROVED,
    )


@pytest.fixture
def completed_order(market, approved_farmer, customer_user, product):
    start = timezone.make_aware(datetime.combine(timezone.localdate(), time(8, 0)))
    order = Order.objects.create(
        customer=customer_user,
        farmer=approved_farmer,
        market=market,
        pickup_date=timezone.localdate(),
        pickup_start_at=start,
        pickup_end_at=start + timedelta(hours=2),
        cutoff_at=start - timedelta(hours=12),
        status=OrderStatus.COMPLETED,
        total_amount="5.00",
    )
    OrderItem.objects.create(
        order=order,
        product=product,
        product_name=product.name,
        unit_price=product.price,
        unit=product.unit,
        quantity=2,
        line_total="5.00",
    )
    return order


@pytest.fixture
def farmer_review(completed_order):
    return FarmerReview.objects.create(
        order=completed_order, rating=2, comment="Stall was hard to find."
    )


@pytest.fixture
def product_review(completed_order):
    return ProductReview.objects.create(
        order_item=completed_order.items.first(), rating=5, comment="Very fresh."
    )
