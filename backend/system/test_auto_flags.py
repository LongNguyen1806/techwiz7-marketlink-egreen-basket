from datetime import datetime, time, timedelta
from unittest import mock

import pytest
from django.core.management import call_command
from django.utils import timezone

from accounts.models import FarmerStatus
from catalog.models import Category, Product, ReviewStatus, Unit
from markets.models import Market
from orders.models import ActorRole, Order, OrderItem, OrderStatus
from orders.services.fsm import transition_order
from reviews.models import FarmerReview, ProductReview
from reviews.selectors import TYPE_PRODUCT
from reviews.services.farmer_reply_service import reply_to_review
from reviews.services.review_service import create_farmer_review, create_product_review
from system.auto_flags import AUTO_PREFIX, check_customer_no_shows, scan_existing
from system.models import FlagTarget, ModerationFlag


@pytest.fixture
def farmer(farmer_user):
    profile = farmer_user.farmer_profile
    profile.status = FarmerStatus.APPROVED
    profile.save(update_fields=["status"])
    return profile


@pytest.fixture
def market(db):
    return Market.objects.create(
        name="Central Market", address="1 Market Street", latitude="10.76", longitude="106.66",
        open_time=time(6, 0), close_time=time(12, 0),
    )


@pytest.fixture
def product(farmer):
    category = Category.objects.create(name="Fruit", display_order=1)
    return Product.objects.create(
        farmer=farmer, category=category, name="Mango", price="2.50", unit=Unit.KG,
        stock_quantity=50, review_status=ReviewStatus.APPROVED,
    )


@pytest.fixture
def make_order(customer_user, farmer, market, product):
    def _make(*, status=OrderStatus.COMPLETED, customer=None, days_ago=1):
        pickup_date = timezone.localdate() - timedelta(days=days_ago)
        start = timezone.make_aware(datetime.combine(pickup_date, time(8, 0)))
        order = Order.objects.create(
            customer=customer or customer_user, farmer=farmer, market=market,
            pickup_date=pickup_date, pickup_start_at=start, pickup_end_at=start + timedelta(hours=2),
            cutoff_at=start - timedelta(hours=12), status=status, total_amount="5.00",
        )
        OrderItem.objects.create(
            order=order, product=product, product_name=product.name, unit=product.unit,
            unit_price=product.price, quantity=2, line_total="5.00",
        )
        return order

    return _make


# The word lists themselves are covered in catalog/test_ai_rules.py. Here the filter is
# stubbed, so the wiring is tested without spelling out offensive words in the code.
FAKE_HIT = ["<offensive word>"]
PROFANITY = "system.auto_flags.find_profanity"


def open_flags(target_type):
    return ModerationFlag.objects.filter(target_type=target_type, resolved_at__isnull=True)


@pytest.mark.django_db
def test_an_offensive_review_goes_to_the_queue(customer_user, make_order):
    order = make_order()

    with mock.patch(PROFANITY, return_value=FAKE_HIT):
        review = create_farmer_review(
            customer=customer_user, order_id=order.pk, rating=1, comment="Terrible stall, never again."
        )

    flag = open_flags(FlagTarget.FARMER_REVIEW).get()
    assert flag.target_id == review.pk
    assert flag.note.startswith(AUTO_PREFIX)
    assert "offensive language" in flag.note
    assert flag.raised_by is None
    # Only queued: the review stays up until an admin decides.
    review.refresh_from_db()
    assert review.is_hidden_by_admin is False


@pytest.mark.django_db
def test_a_phone_number_in_a_review_goes_to_the_queue(customer_user, make_order):
    order = make_order()
    item = order.items.get()

    create_product_review(
        customer=customer_user, order_id=order.pk, item_id=item.pk, rating=5,
        comment="Great! Call me on 0909 123 456 for a cheaper price.",
    )

    assert "contact details" in open_flags(FlagTarget.PRODUCT_REVIEW).get().note


@pytest.mark.django_db
def test_a_clean_review_raises_nothing(customer_user, make_order):
    order = make_order()

    create_farmer_review(customer=customer_user, order_id=order.pk, rating=5, comment="Fresh and friendly.")

    assert not ModerationFlag.objects.exists()


@pytest.mark.django_db
def test_an_abusive_reply_from_the_stall_goes_to_the_queue(customer_user, farmer, make_order):
    order = make_order()
    item = order.items.get()
    review = create_product_review(
        customer=customer_user, order_id=order.pk, item_id=item.pk, rating=2, comment="Too small."
    )

    with mock.patch(PROFANITY, side_effect=lambda text: FAKE_HIT if text == "Then buy elsewhere." else []):
        reply_to_review(
            review_type=TYPE_PRODUCT, review_id=review.pk, farmer_id=farmer.pk, reply="Then buy elsewhere."
        )

    flag = open_flags(FlagTarget.PRODUCT_REVIEW).get()
    assert "stall's reply" in flag.note


@pytest.mark.django_db
def test_repeated_low_ratings_flag_the_product(customer_user, make_order, product):
    comments = ["Sour.", "Not as described.", "Half of them were bruised."]
    for index, comment in enumerate(comments):
        order = make_order(days_ago=index + 1)
        create_product_review(
            customer=customer_user, order_id=order.pk, item_id=order.items.get().pk, rating=1, comment=comment
        )

    flag = open_flags(FlagTarget.PRODUCT).get()
    assert flag.target_id == product.pk
    assert "3 ratings" in flag.note
    assert "Half of them were bruised." in flag.note


@pytest.mark.django_db
def test_two_low_ratings_are_not_enough(customer_user, make_order):
    for days_ago in (1, 2):
        order = make_order(days_ago=days_ago)
        create_product_review(customer=customer_user, order_id=order.pk, item_id=order.items.get().pk, rating=1)

    assert not open_flags(FlagTarget.PRODUCT).exists()


@pytest.mark.django_db
def test_the_third_no_show_flags_the_shopper(customer_user, make_order, farmer, django_capture_on_commit_callbacks):
    for _ in range(2):
        make_order(status=OrderStatus.NO_SHOW)
    ready = make_order(status=OrderStatus.READY_FOR_PICKUP, days_ago=1)  # window already over

    with django_capture_on_commit_callbacks(execute=True):
        transition_order(
            order_id=ready.pk, to_status=OrderStatus.NO_SHOW, actor=farmer.user,
            actor_role=ActorRole.FARMER, expected_version=ready.version,
        )

    flag = open_flags(FlagTarget.CUSTOMER).get()
    assert flag.target_id == customer_user.pk
    assert "3 no-shows" in flag.note


@pytest.mark.django_db
def test_no_shows_outside_the_window_do_not_count(customer_user, make_order):
    for _ in range(3):
        order = make_order(status=OrderStatus.NO_SHOW)
        Order.objects.filter(pk=order.pk).update(created_at=timezone.now() - timedelta(days=45))

    assert check_customer_no_shows(customer_user.pk) is None


@pytest.mark.django_db
def test_one_open_flag_per_thing(customer_user, make_order):
    for _ in range(3):
        make_order(status=OrderStatus.NO_SHOW)

    check_customer_no_shows(customer_user.pk)
    check_customer_no_shows(customer_user.pk)

    assert open_flags(FlagTarget.CUSTOMER).count() == 1


@pytest.mark.django_db
def test_a_broken_queue_never_breaks_the_review(customer_user, make_order):
    order = make_order()

    with mock.patch("system.auto_flags.ModerationFlag.objects.create", side_effect=RuntimeError("down")):
        review = create_farmer_review(
            customer=customer_user, order_id=order.pk, rating=1, comment="Call me on 0909 123 456."
        )

    assert FarmerReview.objects.filter(pk=review.pk).exists()


@pytest.mark.django_db
def test_the_command_flags_what_is_already_there(customer_user, make_order):
    order = make_order()
    ProductReview.objects.create(order_item=order.items.get(), rating=4, comment="Zalo me for a discount")
    for _ in range(3):
        make_order(status=OrderStatus.NO_SHOW)

    call_command("raise_follow_up_flags")

    assert open_flags(FlagTarget.PRODUCT_REVIEW).count() == 1
    assert open_flags(FlagTarget.CUSTOMER).count() == 1
    # Running it again adds nothing.
    assert scan_existing() == {"reviews": 0, "replies": 0, "products": 0, "customers": 0}
