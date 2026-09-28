import os
from datetime import time
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import CustomerProfile, CustomUser, FarmerProfile, FarmerStatus, Role
from catalog.icons import CATEGORY_ICONS
from catalog.models import Category, Product, ProductMarket, Unit
from markets.models import DayOfWeek, FarmerMarket, Market, MarketOperatingDay, PickupSlot
from marketlink_core.policies.roles import RoleCode

DEV_ADMIN_PASSWORD = "Admin@12345"
DEV_DEMO_PASSWORD = "Demo@12345"

# An icon belongs to one category and one only. These six are the generic ones, so they take
# the obvious pictures and the larger demo seed steers around them.
CATEGORIES = [
    ("Vegetables", "carrot"),
    ("Fruits", "apple"),
    ("Dairy & Eggs", "egg"),
    ("Bakery", "croissant"),
    ("Spices", "nut"),
    ("Others", "basket"),
]

MARKETS = [
    {
        "name": "Cho Ben Thanh",
        "address": "Le Loi, Ben Thanh Ward, District 1, Ho Chi Minh City",
        "latitude": Decimal("10.772500"),
        "longitude": Decimal("106.698000"),
        "open_time": time(6, 0),
        "close_time": time(18, 0),
        "days": list(DayOfWeek.values),
    },
    {
        "name": "Cho Ba Chieu",
        "address": "Le Quang Dinh, Ward 14, Binh Thanh District, Ho Chi Minh City",
        "latitude": Decimal("10.803000"),
        "longitude": Decimal("106.701000"),
        "open_time": time(5, 30),
        "close_time": time(12, 0),
        "days": [DayOfWeek.TUESDAY, DayOfWeek.THURSDAY, DayOfWeek.SATURDAY, DayOfWeek.SUNDAY],
    },
]

FARMERS = [
    {
        "email": "farmer1@marketlink.local",
        "stall_name": "Green Leaf Farm",
        "contact_person": "Nguyen Van An",
        "phone": "0901234567",
        "address": "Cu Chi District, Ho Chi Minh City",
        "stalls": [
            {
                "market": "Cho Ben Thanh",
                "stall_label": "Row B, Stall 12, near the main gate",
                "slots": [
                    (DayOfWeek.SATURDAY, time(7, 0), time(10, 0)),
                    (DayOfWeek.SUNDAY, time(7, 0), time(10, 0)),
                    (DayOfWeek.WEDNESDAY, time(15, 0), time(17, 0)),
                ],
            },
        ],
        "products": [
            ("Vegetables", "Organic Tomato", Unit.KG, "2.50", 40, 50),
            ("Vegetables", "Water Spinach", Unit.BUNCH, "0.80", 60, 60),
            ("Vegetables", "Cucumber", Unit.KG, "1.60", 30, 30),
            ("Spices", "Fresh Lemongrass", Unit.BUNCH, "0.50", 25, 30),
            ("Dairy & Eggs", "Free-range Chicken Eggs", Unit.PACK, "3.20", 20, 25),
        ],
    },
    {
        "email": "farmer2@marketlink.local",
        "stall_name": "Sunrise Orchard",
        "contact_person": "Tran Thi Binh",
        "phone": "0912345678",
        "address": "Ben Tre Province",
        "stalls": [
            {
                "market": "Cho Ben Thanh",
                "stall_label": "Row D, Stall 5",
                "slots": [(DayOfWeek.SATURDAY, time(8, 0), time(11, 0))],
            },
            {
                "market": "Cho Ba Chieu",
                "stall_label": "Fruit row, Stall 3",
                "slots": [
                    (DayOfWeek.TUESDAY, time(6, 0), time(9, 0)),
                    (DayOfWeek.SUNDAY, time(6, 0), time(9, 0)),
                ],
            },
        ],
        "products": [
            ("Fruits", "Green-skin Pomelo", Unit.EACH, "2.80", 30, 30),
            ("Fruits", "Dragon Fruit", Unit.KG, "1.90", 45, 50),
            ("Fruits", "Coconut", Unit.EACH, "0.90", 50, 60),
            ("Bakery", "Coconut Candy", Unit.PACK, "2.20", 15, 20),
            ("Others", "Organic Honey", Unit.PACK, "7.50", 0, 10),
        ],
    },
]

CUSTOMER = {
    "email": "customer@marketlink.local",
    "full_name": "Le Minh Chau",
    "phone": "0987654321",
    "address": "12 Nguyen Hue, District 1, Ho Chi Minh City",
}


class Command(BaseCommand):
    help = (
        "Seed the minimum data other branches need to start: 1 admin, 2 markets, "
        "2 approved farmers with stalls and pickup slots, 1 customer, 6 categories and "
        "about 10 products. Safe to run repeatedly; existing records are reused, "
        "and existing passwords are never changed."
    )

    def handle(self, *args, **options):
        admin_email = os.environ.get("SEED_ADMIN_EMAIL", "admin@marketlink.local")
        admin_password = os.environ.get("SEED_ADMIN_PASSWORD")
        demo_password = os.environ.get("SEED_DEMO_PASSWORD")

        # Fallback passwords are for local machines only, never for a deployed server.
        if not settings.DEBUG and not (admin_password and demo_password):
            raise CommandError(
                "SEED_ADMIN_PASSWORD and SEED_DEMO_PASSWORD must be set when DEBUG is False."
            )
        admin_password = admin_password or DEV_ADMIN_PASSWORD
        demo_password = demo_password or DEV_DEMO_PASSWORD

        with transaction.atomic():
            self._seed_admin(admin_email, admin_password)
            categories = self._seed_categories()
            markets = self._seed_markets()
            for farmer in FARMERS:
                self._seed_farmer(farmer, demo_password, markets, categories)
            customer = self._seed_customer(demo_password)
            self._seed_reviews(customer)

        self.stdout.write(self.style.SUCCESS("Minimal seed data is ready."))
        self.stdout.write(f"  Admin    : {admin_email}  (sign in at /admin/login)")
        for farmer in FARMERS:
            self.stdout.write(f"  Farmer   : {farmer['email']}")
        self.stdout.write(f"  Customer : {CUSTOMER['email']}")
        if not os.environ.get("SEED_DEMO_PASSWORD"):
            self.stdout.write(
                f"  Default dev passwords: admin '{DEV_ADMIN_PASSWORD}', others '{DEV_DEMO_PASSWORD}'"
            )

    def _create_user(self, email: str, password: str, role_code: str) -> tuple[CustomUser, bool]:
        user = CustomUser.objects.filter(email=email.strip().lower()).first()
        if user is not None:
            return user, False
        role = Role.objects.get(code=role_code)
        return CustomUser.objects.create_user(email=email, password=password, role=role), True

    def _seed_admin(self, email: str, password: str) -> None:
        if CustomUser.objects.filter(email=email.strip().lower()).exists():
            return
        CustomUser.objects.create_superuser(email=email, password=password)

    def _seed_categories(self) -> dict[str, Category]:
        result = {}
        for order, (name, icon) in enumerate(CATEGORIES, start=1):
            # Freed first: the icon column is unique, so creating the row would fail before
            # there were any rows to reconcile. The column is required too, so a category
            # wearing this picture for want of anything better is moved to another free name
            # rather than emptied.
            squatter = Category.objects.filter(icon=icon).exclude(name=name).first()
            if squatter is not None:
                squatter.icon = self._free_icon()
                squatter.save(update_fields=["icon", "updated_at"])
            category, created = Category.objects.get_or_create(
                name=name, defaults={"icon": icon, "display_order": order}
            )
            if not created and category.icon != icon:
                category.icon = icon
                category.save(update_fields=["icon", "updated_at"])
            result[name] = category
        return result

    def _free_icon(self) -> str:
        used = set(Category.objects.values_list("icon", flat=True))
        for name in CATEGORY_ICONS:
            if name not in used:
                return name
        raise CommandError(
            "Every icon is taken. Add names to catalog/icons.py and the matching pictures to "
            "frontend/src/utils/categoryIcon.js."
        )

    def _seed_markets(self) -> dict[str, Market]:
        result = {}
        for spec in MARKETS:
            market, _ = Market.objects.get_or_create(
                name=spec["name"],
                defaults={
                    "address": spec["address"],
                    "latitude": spec["latitude"],
                    "longitude": spec["longitude"],
                    "open_time": spec["open_time"],
                    "close_time": spec["close_time"],
                },
            )
            for day in spec["days"]:
                MarketOperatingDay.objects.get_or_create(market=market, day_of_week=day)
            result[spec["name"]] = market
        return result

    def _seed_farmer(self, spec, password, markets, categories) -> None:
        user, _ = self._create_user(spec["email"], password, RoleCode.FARMER)
        farmer, _ = FarmerProfile.objects.get_or_create(
            user=user,
            defaults={
                "stall_name": spec["stall_name"],
                "contact_person": spec["contact_person"],
                "phone": spec["phone"],
                "address": spec["address"],
                "status": FarmerStatus.APPROVED,
            },
        )
        for stall in spec["stalls"]:
            market = markets[stall["market"]]
            farmer_market, _ = FarmerMarket.objects.get_or_create(
                farmer=farmer,
                market=market,
                defaults={"stall_label": stall["stall_label"]},
            )
            for day, start, end in stall["slots"]:
                PickupSlot.objects.get_or_create(
                    farmer_market=farmer_market,
                    day_of_week=day,
                    start_time=start,
                    defaults={"end_time": end},
                )
        stalls = list(FarmerMarket.objects.filter(farmer=farmer))
        for category_name, name, unit, price, stock, weekly in spec["products"]:
            product, _ = Product.objects.get_or_create(
                farmer=farmer,
                name=name,
                defaults={
                    "category": categories[category_name],
                    "unit": unit,
                    "price": Decimal(price),
                    "stock_quantity": stock,
                    "weekly_default_quantity": weekly,
                },
            )
            for stall in stalls:
                ProductMarket.objects.get_or_create(product=product, farmer_market=stall)

    def _seed_customer(self, password: str) -> CustomUser:
        user, _ = self._create_user(CUSTOMER["email"], password, RoleCode.CUSTOMER)
        CustomerProfile.objects.get_or_create(
            user=user,
            defaults={
                "full_name": CUSTOMER["full_name"],
                "phone": CUSTOMER["phone"],
                "address": CUSTOMER["address"],
            },
        )
        return user

    # Reviews only exist on completed orders, so the order has to be seeded first. One of them
    # is left hidden on purpose, to give the moderation screen something to restore.
    REVIEWS = [
        {"rating": 5, "product": "Very fresh, picked the same morning.",
         "farmer": "Easy to find and packed everything neatly."},
        {"rating": 4, "product": "Good quality, a couple of bruised ones.",
         "farmer": "Friendly stall, slight wait at collection."},
        {"rating": 2, "product": "Smaller than the photo suggested.",
         "farmer": "Had to call twice before anyone answered."},
        {"rating": 1, "product": "BUY CHEAP PHONES AT 0900xxxxxx",
         "farmer": "Unrelated advertising, kept for the moderation demo."},
    ]

    def _seed_reviews(self, customer: CustomUser) -> None:
        from datetime import datetime, timedelta

        from django.utils import timezone

        from orders.models import Order, OrderItem, OrderStatus
        from reviews.models import FarmerReview, ProductReview

        if FarmerReview.objects.exists() or ProductReview.objects.exists():
            self.stdout.write("  Reviews already present; left untouched.")
            return

        products = list(
            Product.objects.select_related("farmer").order_by("id")[: len(self.REVIEWS)]
        )
        if not products:
            return

        created = 0
        for offset, (product, text) in enumerate(zip(products, self.REVIEWS), start=1):
            market = (
                FarmerMarket.objects.filter(farmer=product.farmer)
                .select_related("market")
                .first()
            )
            if market is None:
                continue

            pickup_date = timezone.localdate() - timedelta(days=offset + 1)
            start = timezone.make_aware(datetime.combine(pickup_date, time(8, 0)))
            order = Order.objects.create(
                customer=customer,
                farmer=product.farmer,
                market=market.market,
                stall_label=market.stall_label,
                pickup_date=pickup_date,
                pickup_start_at=start,
                pickup_end_at=start + timedelta(hours=3),
                cutoff_at=start - timedelta(hours=12),
                status=OrderStatus.COMPLETED,
                total_amount=product.price * 2,
            )
            item = OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                unit_price=product.price,
                unit=product.unit,
                quantity=2,
                line_total=product.price * 2,
            )
            # The last one arrives already hidden, so Restore has something to act on.
            hidden = text["rating"] == 1
            ProductReview.objects.create(
                order_item=item,
                rating=text["rating"],
                comment=text["product"],
                is_hidden_by_admin=hidden,
                hidden_reason="Advertising unrelated to the product." if hidden else None,
                hidden_at=timezone.now() if hidden else None,
            )
            FarmerReview.objects.create(
                order=order,
                rating=text["rating"],
                comment=text["farmer"],
            )
            created += 1

        self.stdout.write(f"  Reviews  : {created} completed orders, each with 2 reviews")
