"""Demo data for exercising the admin screens at a realistic size.

seed_minimal gives a system that works: two stalls, one shopper, a handful of rows. This gives
a system that is worth looking at: around a hundred rows in every table that can hold a
hundred, with every status, every audience and every audit action actually present, so the
filters, the sort selects, the pagination and the two moderation queues all have something to
act on.

Two tables are deliberately smaller, because filling them to a hundred would make the shopper
side absurd rather than realistic: twenty produce categories and twelve markets. Pass
--categories / --markets to override.

Order count is raised to twice --count on purpose. A stall review hangs off a completed order
and a product review off an item of one, so a hundred of each needs more than a hundred
orders; the surplus is what carries the seven non-completed statuses.

Everything written here is reachable from the demo e-mail domain or the demo category and
market names, which is what lets the command replace its own data on every run without
touching anything entered by hand. Re-running it is therefore safe and gives the same result.
"""

import os
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import CustomerProfile, CustomUser, FarmerProfile, FarmerStatus, Role
from catalog.icons import CATEGORY_ICONS
from catalog.models import Category, Product, ProductMarket, ReviewStatus, Unit
from favorites.models import FavoriteFarmer, FavoriteMarket, FavoriteProduct
from marketlink_core.policies.roles import RoleCode
from markets.models import (
    DayOfWeek,
    FarmerClosure,
    FarmerMarket,
    Market,
    MarketClosure,
    MarketOperatingDay,
    PickupSlot,
)
from notifications.models import (
    Announcement,
    AnnouncementAudience,
    Notification,
    NotificationType,
)
from orders.models import (
    ActorRole,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
    Transition,
)
from reviews.models import FarmerReview, ProductReview
from system.models import AuditAction, AuditLog, FlagTarget, ModerationFlag

DEMO_DOMAIN = "demo.marketlink.local"
DEV_DEMO_PASSWORD = "Demo@12345"

# Stalls that actually carry products, and therefore orders. Spreading a hundred products over
# every approved stall would leave each with two, and a three-line order needs three.
PRODUCING_FARMERS = 25

# ---------------------------------------------------------------------------
# Vocabulary. Kept as plain lists so the output reads like a Ho Chi Minh City
# marketplace rather than "Farmer 47".
# ---------------------------------------------------------------------------

FAMILY_NAMES = [
    "Nguyen", "Tran", "Le", "Pham", "Hoang", "Huynh", "Phan", "Vu", "Vo", "Dang",
    "Bui", "Do", "Ho", "Ngo", "Duong", "Ly", "Truong", "Dinh", "Lam", "Mai",
]
MIDDLE_NAMES = ["Van", "Thi", "Minh", "Ngoc", "Thanh", "Quoc", "Huu", "Kim", "Xuan", "Bao"]
GIVEN_NAMES = [
    "An", "Binh", "Chi", "Dung", "Giang", "Ha", "Hai", "Hanh", "Hieu", "Hoa",
    "Hung", "Khanh", "Lan", "Linh", "Long", "Mai", "Nam", "Nga", "Nhung", "Phuc",
    "Quang", "Son", "Tam", "Thao", "Thu", "Tien", "Trang", "Tu", "Tuan", "Yen",
]

STALL_PREFIX = [
    "Vuon", "Trang Trai", "Nong San", "Rau Sach", "Vua Trai Cay", "Ruong", "Hop Tac Xa",
    "Nha Vuon", "Dac San", "Tuoi Moi",
]
STALL_SUFFIX = [
    "Cu Chi", "Hoc Mon", "Binh Chanh", "Da Lat", "Long An", "Tien Giang", "Ben Tre",
    "Dong Nai", "Tay Ninh", "Can Gio", "Vinh Long", "An Giang",
]

DISTRICTS = [
    "District 1", "District 3", "District 4", "District 5", "District 6", "District 7",
    "District 8", "District 10", "District 11", "District 12", "Binh Thanh District",
    "Phu Nhuan District", "Tan Binh District", "Tan Phu District", "Go Vap District",
    "Thu Duc City", "Binh Tan District", "Hoc Mon District", "Cu Chi District",
    "Nha Be District",
]
STREETS = [
    "Nguyen Trai", "Le Loi", "Hai Ba Trung", "Cach Mang Thang Tam", "Dien Bien Phu",
    "Nguyen Thi Minh Khai", "Vo Van Tan", "Pasteur", "Ly Tu Trong", "Truong Chinh",
    "Quang Trung", "Phan Van Tri", "Xo Viet Nghe Tinh", "Nguyen Van Troi", "Hoang Van Thu",
]

# Seventeen categories, all of them things a farm produces. The six generic ones seeded by
# seed_minimal (Vegetables, Fruits, Dairy & Eggs, Bakery, Spices, Others) are deliberately not
# repeated here, and their icons are steered around: an icon belongs to one category only.
CATEGORY_SPECS = [
    ("Leafy greens", "leafy-green"), ("Root vegetables", "salad"),
    ("Gourds & squash", "vegan"), ("Fresh herbs", "leaf"),
    ("Chillies & peppers", "chilli"), ("Mushrooms", "tree"),
    ("Tropical fruit", "banana"), ("Citrus", "citrus"),
    ("Berries", "cherry"), ("Melons", "grape"),
    ("Rice & grains", "wheat"), ("Beans & pulses", "bean"),
    ("Honey & preserves", "flower"), ("Dried goods", "seafood"),
    ("Pickles & ferments", "soup"), ("Fresh fish", "fish"),
    ("Poultry & eggs", "drumstick"),
]
# The last two arrive switched off, so the "Active / Inactive" filter is not showing one state.
INACTIVE_CATEGORIES = {"Pickles & ferments", "Dried goods"}

# Names this command used to create. "Seedlings & plants" is not produce; "Eggs", "Dairy",
# "Bakery" and "Spices" repeated the generic categories seed_minimal already makes.
RETIRED_CATEGORIES = ("Eggs", "Dairy", "Bakery", "Spices", "Seedlings & plants")

# 12 real markets. The last two are closed, so the market filter and the reopen path both have
# a subject.
MARKET_SPECS = [
    ("Cho Ben Thanh", "Le Loi, Ben Thanh Ward, District 1", "10.772500", "106.698000", time(6, 0), time(18, 0)),
    ("Cho Ba Chieu", "Le Quang Dinh, Ward 14, Binh Thanh District", "10.803000", "106.701000", time(5, 30), time(12, 0)),
    ("Cho Tan Dinh", "Hai Ba Trung, Tan Dinh Ward, District 1", "10.790000", "106.690000", time(5, 0), time(17, 0)),
    ("Cho Binh Tay", "Thap Muoi, Ward 2, District 6", "10.750000", "106.650000", time(5, 0), time(19, 0)),
    ("Cho An Dong", "An Duong Vuong, Ward 9, District 5", "10.758000", "106.670000", time(6, 0), time(18, 0)),
    ("Cho Hoa Ho Thi Ky", "Ho Thi Ky, Ward 1, District 10", "10.764000", "106.677000", time(4, 0), time(22, 0)),
    ("Cho Go Vap", "Nguyen Thai Son, Ward 3, Go Vap District", "10.826000", "106.678000", time(5, 0), time(17, 30)),
    ("Cho Thi Nghe", "Xo Viet Nghe Tinh, Ward 19, Binh Thanh District", "10.793000", "106.703000", time(5, 0), time(13, 0)),
    ("Cho Tan Binh", "Ly Thuong Kiet, Ward 8, Tan Binh District", "10.786000", "106.648000", time(5, 30), time(18, 0)),
    ("Cho Phu Nhuan", "Phan Dinh Phung, Ward 1, Phu Nhuan District", "10.799000", "106.680000", time(5, 0), time(14, 0)),
    ("Cho Xom Chieu", "Ton Dan, Ward 14, District 4", "10.757000", "106.705000", time(5, 0), time(12, 0)),
    ("Cho Nga Tu Ga", "Truong Chinh, Trung My Tay Ward, District 12", "10.838000", "106.626000", time(4, 30), time(11, 0)),
]
CLOSED_MARKETS = {"Cho Xom Chieu", "Cho Nga Tu Ga"}

# Product names per category key, so a "Leafy greens" row is not called "Honey".
PRODUCE = {
    "Leafy greens": ["Water spinach", "Bok choy", "Malabar spinach", "Mustard greens", "Amaranth"],
    "Root vegetables": ["Carrot", "White radish", "Sweet potato", "Taro", "Lotus root"],
    "Gourds & squash": ["Bitter melon", "Winter melon", "Luffa", "Chayote", "Pumpkin"],
    "Fresh herbs": ["Coriander", "Vietnamese mint", "Thai basil", "Perilla", "Spring onion"],
    "Chillies & peppers": ["Bird's eye chilli", "Green chilli", "Bell pepper", "Long chilli"],
    "Mushrooms": ["Straw mushroom", "Oyster mushroom", "Enoki", "Wood ear", "Shiitake"],
    "Tropical fruit": ["Mango", "Dragon fruit", "Rambutan", "Longan", "Jackfruit", "Durian"],
    "Citrus": ["Pomelo", "Green orange", "Calamansi", "Lime", "Tangerine"],
    "Berries": ["Mulberry", "Strawberry", "Gac fruit"],
    "Melons": ["Watermelon", "Honeydew", "Cantaloupe"],
    "Rice & grains": ["Jasmine rice", "Brown rice", "Sticky rice", "Corn", "Millet"],
    "Beans & pulses": ["Mung bean", "Black bean", "Peanut", "Soybean", "Long bean"],
    "Honey & preserves": ["Wild honey", "Ginger jam", "Tamarind paste"],
    "Dried goods": ["Dried shrimp", "Dried bamboo", "Dried longan", "Rice paper"],
    "Pickles & ferments": ["Pickled mustard", "Pickled leek", "Salted aubergine"],
    "Fresh fish": ["Tilapia", "Snakehead fish", "Catfish", "River prawn"],
    "Poultry & eggs": ["Chicken eggs", "Duck eggs", "Quail eggs", "Free-range chicken"],
}

PRODUCT_REVIEW_TEXT = [
    "Very fresh, picked the same morning.",
    "Good quality, a couple of bruised ones.",
    "Exactly the weight on the label.",
    "Smaller than the photo suggested.",
    "Kept well for four days in the fridge.",
    "Tasted fine but the packing was wet.",
    "Best I have had this season.",
    "A little pricey for the size.",
    "Arrived slightly wilted.",
    "Will order this every week.",
]
FARMER_REVIEW_TEXT = [
    "Easy to find and packed everything neatly.",
    "Friendly stall, slight wait at collection.",
    "Called ahead to say the order was ready.",
    "Had to queue for fifteen minutes.",
    "Very patient when I changed the pickup time.",
    "Stall was not where the map said.",
    "Clean stall, clear labels on everything.",
    "Short on one item and told me straight away.",
    "Excellent, would recommend to anyone.",
    "Answered my message the same day.",
]
# Text that is meant to be hidden, so the moderation screen has genuine work and Restore has
# something to act on.
SPAM_REVIEW_TEXT = [
    "BUY CHEAP PHONES 0900xxxxxx BEST PRICE",
    "Visit my shop at another site, much cheaper!!!",
    "Call 0911xxxxxx for wholesale, ignore this stall",
]

ANNOUNCEMENT_TOPICS = [
    "Tet holiday collection times",
    "Heavy rain warning for collection",
    "New market joining the platform",
    "Stall relocation notice",
    "Scheduled maintenance window",
    "Updated pickup rules",
    "Reminder: cancel before the cutoff",
    "Seasonal produce now listed",
    "Price display change",
    "Public holiday closures",
]

# One set of notes per kind of flagged thing. Drawing from a single pool put "Shopper
# reported the item was never handed over" on a stall and "Review reads like it was written
# by the stall" on a product, which makes the demo queue read as nonsense.
FLAG_NOTES_BY_TARGET = {
    "PRODUCT": [
        "Photo looks taken from another shop's listing.",
        "Price is an order of magnitude off the others.",
        "Description mentions a phone number.",
        "Category looks wrong for this item.",
    ],
    "PRODUCT_REVIEW": [
        "Review reads like it was written by the stall.",
        "Same text posted on four different products.",
        "Names a competitor and a phone number.",
    ],
    "FARMER_REVIEW": [
        "Review is about the market, not the stall.",
        "Reads like a rival stall left it.",
        "Abusive language about the stallholder.",
    ],
    "FARMER": [
        "Second complaint about weight this month.",
        "Shopper reported the goods were never handed over.",
        "Stall label does not match where it actually trades.",
    ],
    "CUSTOMER": [
        "Three no-shows in a fortnight.",
        "Abusive messages to two different stalls.",
        "Looks like a duplicate of an existing account.",
    ],
}
# Flattened for the purge, which finds this command's own rows by their text.
FLAG_NOTES = [note for notes in FLAG_NOTES_BY_TARGET.values() for note in notes]
# Written the way a refusal has to be written: a stall can only fix what it is told about.
REJECTION_REASONS = [
    "The photo shows a different product from the one described.",
    "The description carries a phone number. Contact details belong on the stall profile.",
    "The category is wrong for this item.",
    "The name claims an organic certification the platform does not verify.",
    "The photo is taken from another shop's listing.",
]

FLAG_RESOLUTIONS = [
    "Called the stall, photo replaced.",
    "Left as is, price is correct for the grade.",
    "Review hidden and the shopper warned.",
    "Stall suspended pending a reply.",
    "No issue found after checking the order.",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/140.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2) Safari/605.1",
    "Mozilla/5.0 (Linux; Android 15) Chrome/139.0 Mobile",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_3) Safari/18.0",
]

# The statuses a hundred-and-something order table should contain, and roughly how much of it
# each should be. COMPLETED dominates because the two review tables feed off it.
STATUS_WEIGHTS = [
    (OrderStatus.COMPLETED, 50),
    (OrderStatus.PLACED, 10),
    (OrderStatus.ACCEPTED, 10),
    (OrderStatus.READY_FOR_PICKUP, 7),
    (OrderStatus.CANCELLED, 7),
    (OrderStatus.DECLINED, 6),
    (OrderStatus.NO_SHOW, 6),
    (OrderStatus.EXPIRED, 4),
]
OPEN_FOR_SEED = {OrderStatus.PLACED, OrderStatus.ACCEPTED, OrderStatus.READY_FOR_PICKUP}

# from_status / transition / actor role for each terminal status, so the order timeline on the
# admin lookup screen is a real path and not a single row.
STATUS_PATHS = {
    OrderStatus.PLACED: [],
    OrderStatus.ACCEPTED: [(OrderStatus.PLACED, OrderStatus.ACCEPTED, Transition.T2, ActorRole.FARMER)],
    OrderStatus.READY_FOR_PICKUP: [
        (OrderStatus.PLACED, OrderStatus.ACCEPTED, Transition.T2, ActorRole.FARMER),
        (OrderStatus.ACCEPTED, OrderStatus.READY_FOR_PICKUP, Transition.T9, ActorRole.FARMER),
    ],
    OrderStatus.COMPLETED: [
        (OrderStatus.PLACED, OrderStatus.ACCEPTED, Transition.T2, ActorRole.FARMER),
        (OrderStatus.ACCEPTED, OrderStatus.READY_FOR_PICKUP, Transition.T9, ActorRole.FARMER),
        (OrderStatus.READY_FOR_PICKUP, OrderStatus.COMPLETED, Transition.T10, ActorRole.FARMER),
    ],
    OrderStatus.NO_SHOW: [
        (OrderStatus.PLACED, OrderStatus.ACCEPTED, Transition.T2, ActorRole.FARMER),
        (OrderStatus.ACCEPTED, OrderStatus.READY_FOR_PICKUP, Transition.T9, ActorRole.FARMER),
        (OrderStatus.READY_FOR_PICKUP, OrderStatus.NO_SHOW, Transition.T11, ActorRole.FARMER),
    ],
    OrderStatus.CANCELLED: [(OrderStatus.PLACED, OrderStatus.CANCELLED, Transition.T5, ActorRole.CUSTOMER)],
    OrderStatus.DECLINED: [(OrderStatus.PLACED, OrderStatus.DECLINED, Transition.T3, ActorRole.FARMER)],
    OrderStatus.EXPIRED: [(OrderStatus.PLACED, OrderStatus.EXPIRED, Transition.T8, ActorRole.SYSTEM)],
}


def weighted_statuses(total: int) -> list[str]:
    """Expand STATUS_WEIGHTS to exactly `total` entries."""
    share = sum(weight for _, weight in STATUS_WEIGHTS)
    out: list[str] = []
    for status, weight in STATUS_WEIGHTS:
        out.extend([status] * (total * weight // share))
    # Rounding leaves a few short; completed orders are the ones worth having more of.
    while len(out) < total:
        out.append(OrderStatus.COMPLETED)
    return out[:total]


class Command(BaseCommand):
    help = (
        "Fill the database with around a hundred rows per table, covering every status, so the "
        "admin screens can be tested at a realistic size."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--count", type=int, default=100,
            help="Rows per table for the tables that can hold a hundred (default 100).",
        )
        parser.add_argument(
            "--categories", type=int, default=len(CATEGORY_SPECS),
            help="Produce categories (default 20; a hundred would make the shopper side absurd).",
        )
        parser.add_argument(
            "--markets", type=int, default=len(MARKET_SPECS),
            help="Markets (default 12, all real Ho Chi Minh City markets).",
        )
        parser.add_argument(
            "--random-seed", type=int, default=20260927,
            help="Fixed so two runs produce the same data. Change it for a different shuffle.",
        )

    # ------------------------------------------------------------------ entry

    def handle(self, *args, **options):
        count = options["count"]
        if count < 1:
            raise CommandError("--count must be at least 1.")
        if options["categories"] > len(CATEGORY_SPECS):
            raise CommandError(f"--categories cannot exceed {len(CATEGORY_SPECS)}.")
        if options["markets"] > len(MARKET_SPECS):
            raise CommandError(f"--markets cannot exceed {len(MARKET_SPECS)}.")

        password = os.environ.get("SEED_DEMO_PASSWORD")
        if not settings.DEBUG and not password:
            raise CommandError("SEED_DEMO_PASSWORD must be set when DEBUG is False.")
        password = password or DEV_DEMO_PASSWORD

        self.rng = random.Random(options["random_seed"])
        self.count = count
        self.today = timezone.localdate()
        self.now = timezone.now()
        # Hashed once. Two hundred calls to set_password would spend a minute in PBKDF2 for no
        # benefit, since every demo account shares the same password anyway.
        self.password_hash = make_password(password)

        with transaction.atomic():
            # Always, so the command is safe to re-run: a second pass without this appended a
            # fresh set of stalls, slots and favourites on top of the first.
            self._purge()
            admin = self._admin_user()
            categories = self._seed_categories(options["categories"])
            markets = self._seed_markets(options["markets"])
            customers = self._seed_customers(count)
            farmers = self._seed_farmers(count, markets)
            products = self._seed_products(count, farmers, categories, admin)
            orders = self._seed_orders(count * 2, farmers, products)
            self._seed_reviews(count, orders, admin)
            self._seed_favorites(count, customers, farmers, products, markets)
            self._seed_notifications(count, customers, farmers)
            self._seed_announcements(count, admin)
            self._seed_closures(count, markets, farmers)
            self._seed_audit_logs(count, admin, customers, farmers)
            self._seed_flags(count, admin, products)

        self.stdout.write(self.style.SUCCESS("Demo data is ready."))
        self._report()
        self.stdout.write(f"  Every demo account signs in with: {password}")
        self.stdout.write(f"  Customers: shopper1@{DEMO_DOMAIN} ... shopper{count}@{DEMO_DOMAIN}")
        self.stdout.write(f"  Farmers  : stall1@{DEMO_DOMAIN} ... stall{count}@{DEMO_DOMAIN}")

    # ------------------------------------------------------------------ purge

    def _purge(self) -> None:
        """Remove what a previous run wrote, children first because the FKs are RESTRICT.

        Nothing outside the demo e-mail domain and the demo category / market names is touched,
        and a market or category that something real still points at is left alone.
        """
        users = CustomUser.objects.filter(email__endswith=f"@{DEMO_DOMAIN}")
        user_ids = list(users.values_list("id", flat=True))
        farmer_ids = list(
            FarmerProfile.objects.filter(user_id__in=user_ids).values_list("user_id", flat=True)
        )
        market_ids = list(
            Market.objects.filter(name__in=[spec[0] for spec in MARKET_SPECS]).values_list(
                "id", flat=True
            )
        )
        order_ids = list(
            Order.objects.filter(customer_id__in=user_ids).values_list("id", flat=True)
        )

        ProductReview.objects.filter(order_item__order_id__in=order_ids).delete()
        FarmerReview.objects.filter(order_id__in=order_ids).delete()
        OrderStatusHistory.objects.filter(order_id__in=order_ids).delete()
        OrderItem.objects.filter(order_id__in=order_ids).delete()
        Order.objects.filter(id__in=order_ids).delete()

        FavoriteProduct.objects.filter(customer_id__in=user_ids).delete()
        FavoriteFarmer.objects.filter(customer_id__in=user_ids).delete()
        FavoriteMarket.objects.filter(customer_id__in=user_ids).delete()
        # A favourite pointing at a demo stall or market from a non-demo shopper would block the
        # RESTRICT delete below.
        FavoriteFarmer.objects.filter(farmer_id__in=farmer_ids).delete()
        FavoriteMarket.objects.filter(market_id__in=market_ids).delete()
        FavoriteProduct.objects.filter(product__farmer_id__in=farmer_ids).delete()

        Notification.objects.filter(recipient_id__in=user_ids).delete()
        Announcement.objects.filter(title__in=ANNOUNCEMENT_TOPICS).delete()
        AuditLog.objects.filter(user_id__in=user_ids).delete()

        Product.objects.filter(farmer_id__in=farmer_ids).delete()
        FarmerClosure.objects.filter(farmer_id__in=farmer_ids).delete()
        PickupSlot.objects.filter(farmer_market__farmer_id__in=farmer_ids).delete()
        FarmerMarket.objects.filter(farmer_id__in=farmer_ids).delete()
        FarmerProfile.objects.filter(user_id__in=user_ids).delete()
        CustomerProfile.objects.filter(user_id__in=user_ids).delete()
        users.delete()

        MarketClosure.objects.filter(market_id__in=market_ids).delete()
        # Markets and categories only go if nothing outside the demo still points at them.
        for market in Market.objects.filter(id__in=market_ids):
            if market.orders.exists() or market.farmer_markets.exists():
                continue
            MarketOperatingDay.objects.filter(market=market).delete()
            market.delete()
        # Retired names included: an earlier version of this command created categories that
        # are no longer produce, or that duplicated the generic ones from seed_minimal. Left
        # out of the purge they would sit in the list for ever, because nothing else knows
        # this command put them there.
        Category.objects.filter(
            name__in=[spec[0] for spec in CATEGORY_SPECS] + list(RETIRED_CATEGORIES),
            products__isnull=True,
        ).delete()
        # Last, because it is decided by what the deletions above left behind.
        self._purge_orphan_flags()
        self.stdout.write("  Previous demo data removed.")

    def _purge_orphan_flags(self) -> None:
        """Drop queue entries whose target no longer exists.

        Matching on the note text was not enough: a previous run's wording stops matching the
        moment those sample notes are edited, and the stale rows then sit in the queue for
        ever. A flag pointing at a row that has just been deleted is demo litter by
        definition, and one pointing at something real is left alone whoever raised it.
        """
        from accounts.models import CustomerProfile, FarmerProfile
        from catalog.models import Product
        from reviews.models import FarmerReview, ProductReview

        models_by_kind = {
            FlagTarget.PRODUCT: Product,
            FlagTarget.PRODUCT_REVIEW: ProductReview,
            FlagTarget.FARMER_REVIEW: FarmerReview,
            FlagTarget.FARMER: FarmerProfile,
            FlagTarget.CUSTOMER: CustomerProfile,
        }
        orphans: list[int] = []
        for kind, model in models_by_kind.items():
            wanted = set(
                ModerationFlag.objects.filter(target_type=kind).values_list("target_id", flat=True)
            )
            if not wanted:
                continue
            alive = set(model.objects.filter(pk__in=wanted).values_list("pk", flat=True))
            missing = wanted - alive
            if missing:
                orphans.extend(
                    ModerationFlag.objects.filter(
                        target_type=kind, target_id__in=missing
                    ).values_list("id", flat=True)
                )
        if orphans:
            ModerationFlag.objects.filter(id__in=orphans).delete()

    # ------------------------------------------------------------- foundations

    def _admin_user(self) -> CustomUser:
        admin = CustomUser.objects.filter(role__code=RoleCode.ADMIN).order_by("id").first()
        if admin is None:
            raise CommandError("No admin account exists. Run `manage.py seed_minimal` first.")
        return admin

    def _seed_categories(self, wanted: int) -> list[Category]:
        result = []
        for order, (name, icon) in enumerate(CATEGORY_SPECS[:wanted], start=1):
            # Freed first, not afterwards: a category from an earlier seed may be holding
            # this picture, and the icon column is unique, so creating the row would fail
            # before there were any rows to reconcile.
            self._claim_icon(icon, for_name=name)
            category, created = Category.objects.get_or_create(
                name=name,
                defaults={
                    "icon": icon,
                    "display_order": order,
                    "is_active": name not in INACTIVE_CATEGORIES,
                },
            )
            if not created and category.icon != icon:
                category.icon = icon
                category.save(update_fields=["icon", "updated_at"])
            result.append(category)
        self.counts = {"Categories": len(result)}
        return result

    def _claim_icon(self, icon: str, *, for_name: str) -> None:
        """Move whoever else is wearing this icon onto a free one."""
        holder = Category.objects.filter(icon=icon).exclude(name=for_name).first()
        if holder is None:
            return
        holder.icon = self._free_icon()
        holder.save(update_fields=["icon", "updated_at"])

    def _free_icon(self) -> str:
        used = set(Category.objects.values_list("icon", flat=True))
        for name in CATEGORY_ICONS:
            if name not in used:
                return name
        raise CommandError(
            "Every icon is taken. Add names to catalog/icons.py and the matching pictures to "
            "frontend/src/utils/categoryIcon.js."
        )

    def _seed_markets(self, wanted: int) -> list[Market]:
        result = []
        for name, address, lat, lng, opens, closes in MARKET_SPECS[:wanted]:
            market, created = Market.objects.get_or_create(
                name=name,
                defaults={
                    "address": f"{address}, Ho Chi Minh City",
                    "latitude": Decimal(lat),
                    "longitude": Decimal(lng),
                    "open_time": opens,
                    "close_time": closes,
                    "is_active": name not in CLOSED_MARKETS,
                },
            )
            if created:
                # Every market opens at the weekend; the rest of the week varies, so the
                # operating-day filter separates them.
                days = {DayOfWeek.SATURDAY, DayOfWeek.SUNDAY}
                days.update(self.rng.sample(list(DayOfWeek.values)[:5], self.rng.randint(2, 5)))
                for day in sorted(days):
                    MarketOperatingDay.objects.get_or_create(market=market, day_of_week=day)
            result.append(market)
        self.counts["Markets"] = len(result)
        return result

    # ------------------------------------------------------------------ people

    def _person_name(self) -> str:
        return " ".join(
            (
                self.rng.choice(FAMILY_NAMES),
                self.rng.choice(MIDDLE_NAMES),
                self.rng.choice(GIVEN_NAMES),
            )
        )

    def _address(self) -> str:
        return (
            f"{self.rng.randint(1, 480)} {self.rng.choice(STREETS)}, "
            f"{self.rng.choice(DISTRICTS)}, Ho Chi Minh City"
        )

    def _make_users(self, prefix: str, role_code: str, total: int) -> list[CustomUser]:
        role = Role.objects.get(code=role_code)
        emails = [f"{prefix}{n}@{DEMO_DOMAIN}" for n in range(1, total + 1)]
        existing = dict(
            CustomUser.objects.filter(email__in=emails).values_list("email", "id")
        )
        to_create = [
            CustomUser(
                email=email,
                role=role,
                password=self.password_hash,
                is_active=True,
                # A spread of join dates, so "newest first" and any date filter mean something.
                last_login=self.now - timedelta(days=self.rng.randint(0, 120)),
            )
            for email in emails
            if email not in existing
        ]
        CustomUser.objects.bulk_create(to_create, batch_size=200)
        by_email = {u.email: u for u in CustomUser.objects.filter(email__in=emails)}
        return [by_email[email] for email in emails]

    def _seed_customers(self, total: int) -> list[CustomUser]:
        users = self._make_users("shopper", RoleCode.CUSTOMER, total)
        have = set(
            CustomerProfile.objects.filter(user__in=users).values_list("user_id", flat=True)
        )
        profiles = []
        locked = []
        for index, user in enumerate(users, start=1):
            if user.id in have:
                continue
            # Every tenth shopper is locked, with the reason the admin screen expects to show.
            is_locked = index % 10 == 0
            profiles.append(
                CustomerProfile(
                    user=user,
                    full_name=self._person_name(),
                    phone=f"09{index:08d}",
                    address=self._address(),
                    deactivation_reason=(
                        "Repeated no-shows at collection." if is_locked else None
                    ),
                )
            )
            if is_locked:
                locked.append(user.id)
        CustomerProfile.objects.bulk_create(profiles, batch_size=200)
        CustomUser.objects.filter(id__in=locked).update(is_active=False)
        self.counts["Customers"] = len(users)
        return users

    def _seed_farmers(self, total: int, markets: list[Market]) -> list[FarmerProfile]:
        users = self._make_users("stall", RoleCode.FARMER, total)
        have = set(
            FarmerProfile.objects.filter(user__in=users).values_list("user_id", flat=True)
        )
        # Every status is present and none of them is a rounding error: the queue screens need
        # pending stalls, the moderation screens need suspended ones.
        statuses = (
            [FarmerStatus.APPROVED] * 60
            + [FarmerStatus.PENDING] * 20
            + [FarmerStatus.SUSPENDED] * 10
            + [FarmerStatus.REJECTED] * 10
        )
        reasons = {
            FarmerStatus.SUSPENDED: "Suspended after three unresolved complaints.",
            FarmerStatus.REJECTED: "Business licence did not match the stall name.",
        }
        active_markets = [m for m in markets if m.is_active] or markets

        profiles = []
        for index, user in enumerate(users, start=1):
            if user.id in have:
                continue
            status = statuses[(index - 1) % len(statuses)]
            # Coordinates on most but not all, because the CHECK constraint allows both-or-none
            # and the map on the shopper side has to cope with a stall that has neither.
            with_coords = index % 7 != 0
            profiles.append(
                FarmerProfile(
                    user=user,
                    stall_name=(
                        f"{self.rng.choice(STALL_PREFIX)} {self.rng.choice(STALL_SUFFIX)} "
                        f"{index}"
                    ),
                    contact_person=self._person_name(),
                    phone=f"08{index:08d}",
                    address=self._address(),
                    description=(
                        "Family plot, third generation. Harvest the morning of collection."
                        if index % 3
                        else None
                    ),
                    latitude=Decimal(f"10.{self.rng.randint(700000, 860000)}") if with_coords else None,
                    longitude=Decimal(f"106.{self.rng.randint(600000, 780000)}") if with_coords else None,
                    status=status,
                    status_reason=reasons.get(status),
                    order_cutoff_hours=self.rng.choice([1, 4, 6, 12, 24, 36, 48, 72]),
                    operating_days=sorted(
                        self.rng.sample(list(DayOfWeek.values), self.rng.randint(2, 6))
                    ),
                )
            )
        FarmerProfile.objects.bulk_create(profiles, batch_size=200)
        farmers = list(
            FarmerProfile.objects.filter(user__in=users).select_related("user").order_by("user_id")
        )

        # Stalls that trade need a pitch and collection windows. Pending and rejected ones do
        # not: an admin reviewing them should see exactly that.
        tradeable = [f for f in farmers if f.status in (FarmerStatus.APPROVED, FarmerStatus.SUSPENDED)]
        existing_pairs = set(
            FarmerMarket.objects.filter(farmer__in=tradeable).values_list("farmer_id", "market_id")
        )
        links = []
        for farmer in tradeable:
            for market in [self.rng.choice(active_markets)]:
                if (farmer.user_id, market.id) in existing_pairs:
                    continue
                existing_pairs.add((farmer.user_id, market.id))
                links.append(
                    FarmerMarket(
                        farmer=farmer,
                        market=market,
                        stall_label=(
                            f"Row {self.rng.choice('ABCDEF')}, Stall "
                            f"{self.rng.randint(1, 60)}"
                        ),
                    )
                )
        FarmerMarket.objects.bulk_create(links, batch_size=200, ignore_conflicts=True)

        slots = []
        seen_slots = set()
        for link in FarmerMarket.objects.filter(farmer__in=tradeable).select_related("market"):
            for day in self.rng.sample(list(DayOfWeek.values), 3):
                start = time(self.rng.choice([6, 7, 8, 14, 15]), self.rng.choice([0, 30]))
                key = (link.id, day, start)
                if key in seen_slots:
                    continue
                seen_slots.add(key)
                slots.append(
                    PickupSlot(
                        farmer_market=link,
                        day_of_week=day,
                        start_time=start,
                        end_time=time(start.hour + 2, start.minute),
                        # A few switched off, so the slot list is not uniformly green.
                        is_active=self.rng.random() > 0.15,
                    )
                )
        PickupSlot.objects.bulk_create(slots, batch_size=300, ignore_conflicts=True)

        self.counts["Farmers"] = len(farmers)
        self.counts["Farmer stalls (farmer_markets)"] = FarmerMarket.objects.filter(
            farmer__in=tradeable
        ).count()
        self.counts["Pickup slots"] = PickupSlot.objects.filter(
            farmer_market__farmer__in=tradeable
        ).count()
        return farmers

    # --------------------------------------------------------------- catalogue

    def _seed_products(
        self, total: int, farmers: list[FarmerProfile], categories: list[Category], admin: CustomUser
    ) -> list[Product]:
        producers = [f for f in farmers if f.status == FarmerStatus.APPROVED][:PRODUCING_FARMERS]
        if not producers:
            return []
        if Product.objects.filter(farmer__in=producers).exists():
            self.counts["Products"] = Product.objects.filter(farmer__in=producers).count()
            return list(Product.objects.filter(farmer__in=producers).select_related("farmer"))

        rows = []
        for index in range(total):
            farmer = producers[index % len(producers)]
            category = categories[index % len(categories)]
            names = PRODUCE.get(category.name) or [category.name]
            hidden = index % 12 == 0
            archived = index % 25 == 0
            # A tenth are out of stock, which is what makes the stock filter and the
            # "sold out" path on the shopper side testable.
            out_of_stock = index % 10 == 0
            # Roughly a third of the catalogue is waiting and a tenth was refused, so the
            # approval queue is worth opening the moment the seed finishes and the "Refused"
            # filter has more than a token row behind it.
            if index % 3 == 0:
                review_status = ReviewStatus.PENDING
                review_note = None
            elif index % 10 == 0:
                review_status = ReviewStatus.REJECTED
                review_note = self.rng.choice(REJECTION_REASONS)
            else:
                review_status = ReviewStatus.APPROVED
                review_note = None
            rows.append(
                Product(
                    farmer=farmer,
                    category=category,
                    name=f"{names[index // len(categories) % len(names)]} ({farmer.user_id})",
                    description="Grown without chemical sprays. Weighed at the stall.",
                    price=Decimal(self.rng.randrange(800, 250_000, 500)) / 100,
                    unit=self.rng.choice(list(Unit.values)),
                    stock_quantity=0 if out_of_stock else self.rng.randint(5, 400),
                    weekly_default_quantity=self.rng.choice([None, 10, 20, 50]),
                    is_available=not out_of_stock,
                    is_archived=archived,
                    review_status=review_status,
                    review_note=review_note,
                    reviewed_at=self.now - timedelta(days=self.rng.randint(1, 40))
                    if review_status != ReviewStatus.PENDING
                    else None,
                    reviewed_by=admin if review_status != ReviewStatus.PENDING else None,
                    is_hidden_by_admin=hidden,
                    hidden_reason="Photo does not match the item described." if hidden else None,
                    hidden_at=self.now - timedelta(days=self.rng.randint(1, 30)) if hidden else None,
                    hidden_by=admin if hidden else None,
                )
            )
        Product.objects.bulk_create(rows, batch_size=200)
        products = list(
            Product.objects.filter(farmer__in=producers).select_related("farmer").order_by("id")
        )
        stalls_by_farmer: dict[int, list[int]] = {}
        for stall_id, farmer_id in FarmerMarket.objects.filter(farmer__in=producers).values_list("id", "farmer_id"):
            stalls_by_farmer.setdefault(farmer_id, []).append(stall_id)
        ProductMarket.objects.bulk_create(
            [
                ProductMarket(product_id=product.pk, farmer_market_id=stall_id)
                for product in products
                for stall_id in stalls_by_farmer.get(product.farmer_id, [])
            ],
            batch_size=500,
            ignore_conflicts=True,
        )
        self._spread_created_at(Product, len(products), 180)
        self.counts["Products"] = len(products)
        return products

    # ------------------------------------------------------------------ orders

    def _seed_orders(
        self, total: int, farmers: list[FarmerProfile], products: list[Product]
    ) -> list[Order]:
        customers = list(
            CustomUser.objects.filter(email__endswith=f"@{DEMO_DOMAIN}", role__code=RoleCode.CUSTOMER)
            .order_by("id")
        )
        by_farmer: dict[int, list[Product]] = {}
        for product in products:
            by_farmer.setdefault(product.farmer_id, []).append(product)
        if not customers or not by_farmer:
            return []
        if Order.objects.filter(customer__in=customers).exists():
            orders = list(Order.objects.filter(customer__in=customers).order_by("id"))
            self.counts["Orders"] = len(orders)
            return orders

        slots_by_farmer: dict[int, list[PickupSlot]] = {}
        for slot in PickupSlot.objects.filter(
            farmer_market__farmer_id__in=by_farmer, is_active=True
        ).select_related("farmer_market", "farmer_market__market"):
            slots_by_farmer.setdefault(slot.farmer_market.farmer_id, []).append(slot)
        cutoffs = {f.user_id: f.order_cutoff_hours for f in farmers}

        statuses = weighted_statuses(total)
        self.rng.shuffle(statuses)

        orders: list[Order] = []
        plans: list[tuple[Order, list[Product]]] = []
        for index, status in enumerate(statuses):
            farmer_id = list(by_farmer)[index % len(by_farmer)]
            slots = slots_by_farmer.get(farmer_id)
            if not slots:
                continue
            slot = self.rng.choice(slots)
            pickup_date = self._date_on_weekday(
                slot.day_of_week, future=status in OPEN_FOR_SEED
            )
            start = timezone.make_aware(datetime.combine(pickup_date, slot.start_time))
            end = timezone.make_aware(datetime.combine(pickup_date, slot.end_time))
            chosen = self.rng.sample(
                by_farmer[farmer_id], min(3, len(by_farmer[farmer_id]))
            )
            lines = [(p, self.rng.randint(1, 5)) for p in chosen]
            total_amount = sum(p.price * q for p, q in lines)
            order = Order(
                customer=customers[index % len(customers)],
                farmer_id=farmer_id,
                market=slot.farmer_market.market,
                pickup_slot=slot,
                stall_label=slot.farmer_market.stall_label,
                pickup_date=pickup_date,
                pickup_start_at=start,
                pickup_end_at=end,
                cutoff_at=start - timedelta(hours=cutoffs.get(farmer_id, 12)),
                status=status,
                note=self.rng.choice(
                    [None, "Please pack the herbs separately.", "I will come at the late end."]
                ),
                total_amount=total_amount,
            )
            # Saved one at a time, not in bulk: the lines and the status timeline below need the
            # id, and MySQL cannot report the ids a bulk insert assigned. It also gives each
            # order its simple-history row, which the admin change log reads.
            order.save()
            orders.append(order)
            plans.append((order, lines))

        items = []
        history = []
        for order, lines in plans:
            for product, quantity in lines:
                items.append(
                    OrderItem(
                        order=order,
                        product=product,
                        product_name=product.name,
                        unit=product.unit,
                        unit_price=product.price,
                        quantity=quantity,
                        line_total=product.price * quantity,
                    )
                )
            # Every order starts with its own creation row, then walks the path its status implies.
            history.append(
                OrderStatusHistory(
                    order=order,
                    from_status=None,
                    to_status=OrderStatus.PLACED,
                    transition=Transition.T1,
                    actor=order.customer,
                    actor_role=ActorRole.CUSTOMER,
                )
            )
            for from_status, to_status, transition, actor_role in STATUS_PATHS[order.status]:
                history.append(
                    OrderStatusHistory(
                        order=order,
                        from_status=from_status,
                        to_status=to_status,
                        transition=transition,
                        actor=None if actor_role == ActorRole.SYSTEM else order.customer,
                        actor_role=actor_role,
                        change_reason=(
                            "Not collected before the window closed."
                            if to_status == OrderStatus.NO_SHOW
                            else None
                        ),
                    )
                )
        OrderItem.objects.bulk_create(items, batch_size=400)
        OrderStatusHistory.objects.bulk_create(history, batch_size=400)

        # Placed before the collection day, which is what any date filter on the list assumes.
        for order in orders:
            order.created_at = timezone.make_aware(
                datetime.combine(
                    order.pickup_date - timedelta(days=self.rng.randint(1, 10)),
                    time(self.rng.randint(7, 21), self.rng.randint(0, 59)),
                )
            )
        Order.objects.bulk_update(orders, ["created_at"], batch_size=200)

        self.counts["Orders"] = len(orders)
        self.counts["Order lines"] = len(items)
        self.counts["Order status history"] = len(history)
        return orders

    def _date_on_weekday(self, day_of_week: int, *, future: bool) -> date:
        """The nearest date matching that ISO weekday, forward or back."""
        if future:
            base = self.today + timedelta(days=self.rng.randint(1, 21))
            return base + timedelta(days=(day_of_week - base.isoweekday()) % 7)
        base = self.today - timedelta(days=self.rng.randint(2, 150))
        return base - timedelta(days=(base.isoweekday() - day_of_week) % 7)

    # ----------------------------------------------------------------- reviews

    def _seed_reviews(self, total: int, orders: list[Order], admin: CustomUser) -> None:
        completed = [o for o in orders if o.status == OrderStatus.COMPLETED]
        if not completed:
            return
        if FarmerReview.objects.filter(order__in=completed).exists():
            return

        # Stall reviews: one per completed order, and deliberately not on all of them, because
        # an unreviewed completed order is the normal case.
        stall_rows = []
        for index, order in enumerate(completed[:total]):
            spam = index % 15 == 0
            rating = 1 if spam else self._skewed_rating()
            stall_rows.append(
                FarmerReview(
                    order=order,
                    rating=rating,
                    comment=(
                        SPAM_REVIEW_TEXT[index % len(SPAM_REVIEW_TEXT)]
                        if spam
                        else FARMER_REVIEW_TEXT[index % len(FARMER_REVIEW_TEXT)]
                    ),
                    reply="Thank you, we will look into it." if index % 4 == 0 else None,
                    replied_at=self.now - timedelta(days=self.rng.randint(1, 20))
                    if index % 4 == 0
                    else None,
                    is_hidden_by_admin=spam,
                    hidden_reason="Advertising unrelated to the stall." if spam else None,
                    hidden_at=self.now - timedelta(days=self.rng.randint(1, 20)) if spam else None,
                    hidden_by=admin if spam else None,
                )
            )
        FarmerReview.objects.bulk_create(stall_rows, batch_size=200)

        # Product reviews hang off a line, not an order, so a completed three-line order can
        # carry up to three.
        items = list(
            OrderItem.objects.filter(order__in=completed)
            .exclude(product_review__isnull=False)
            .order_by("id")[:total]
        )
        product_rows = []
        for index, item in enumerate(items):
            spam = index % 18 == 0
            product_rows.append(
                ProductReview(
                    order_item=item,
                    rating=1 if spam else self._skewed_rating(),
                    comment=(
                        SPAM_REVIEW_TEXT[index % len(SPAM_REVIEW_TEXT)]
                        if spam
                        else PRODUCT_REVIEW_TEXT[index % len(PRODUCT_REVIEW_TEXT)]
                    ),
                    reply="Sorry about that, we have changed supplier." if index % 6 == 0 else None,
                    replied_at=self.now - timedelta(days=self.rng.randint(1, 20))
                    if index % 6 == 0
                    else None,
                    is_hidden_by_admin=spam,
                    hidden_reason="Advertising unrelated to the product." if spam else None,
                    hidden_at=self.now - timedelta(days=self.rng.randint(1, 20)) if spam else None,
                    hidden_by=admin if spam else None,
                )
            )
        ProductReview.objects.bulk_create(product_rows, batch_size=200)

        self._spread_created_at(FarmerReview, len(stall_rows), 150)
        self._spread_created_at(ProductReview, len(product_rows), 150)
        self.counts["Stall reviews"] = len(stall_rows)
        self.counts["Product reviews"] = len(product_rows)

    def _skewed_rating(self) -> int:
        """Mostly 4 and 5, the way a real marketplace looks, with enough 1s and 2s to sort by."""
        return self.rng.choices([1, 2, 3, 4, 5], weights=[6, 8, 14, 32, 40])[0]

    # --------------------------------------------------------------- favorites

    def _seed_favorites(self, total, customers, farmers, products, markets) -> None:
        tradeable = [f for f in farmers if f.status == FarmerStatus.APPROVED]
        if not (customers and tradeable and products):
            return
        made = {}
        for label, model, field, pool in (
            ("Favourite stalls", FavoriteFarmer, "farmer", tradeable),
            ("Favourite products", FavoriteProduct, "product", products),
            ("Favourite markets", FavoriteMarket, "market", markets),
        ):
            seen = set()
            rows = []
            while len(rows) < total and len(seen) < len(customers) * len(pool):
                customer = self.rng.choice(customers)
                target = self.rng.choice(pool)
                key = (customer.id, target.pk)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(model(customer=customer, **{field: target}))
            model.objects.bulk_create(rows, batch_size=200, ignore_conflicts=True)
            made[label] = len(rows)
        self.counts.update(made)

    # ----------------------------------------------------------- notifications

    def _seed_notifications(self, total, customers, farmers) -> None:
        farmer_users = [f.user for f in farmers]
        recipients = customers + farmer_users
        if not recipients:
            return
        types = list(NotificationType.values)
        rows = []
        for index in range(total):
            read = index % 3 != 0
            notification_type = types[index % len(types)]
            created = self.now - timedelta(
                days=self.rng.randint(0, 45), hours=self.rng.randint(0, 23)
            )
            rows.append(
                Notification(
                    recipient=recipients[index % len(recipients)],
                    type=notification_type,
                    title=NotificationType(notification_type).label,
                    message=(
                        f"{NotificationType(notification_type).label} — order "
                        f"#{self.rng.randint(1000, 9999)}."
                    ),
                    target_url=f"/orders/{self.rng.randint(1, 200)}",
                    is_read=read,
                    read_at=created + timedelta(hours=2) if read else None,
                )
            )
        Notification.objects.bulk_create(rows, batch_size=200)
        self._spread_created_at(Notification, len(rows), 45)
        self.counts["Notifications"] = len(rows)

    def _seed_announcements(self, total, admin) -> None:
        if Announcement.objects.filter(title__in=ANNOUNCEMENT_TOPICS).count() >= total:
            return
        audiences = list(AnnouncementAudience.values)
        rows = []
        for index in range(total):
            topic = ANNOUNCEMENT_TOPICS[index % len(ANNOUNCEMENT_TOPICS)]
            # A third in the past, a third running now, a third scheduled — the three cases the
            # announcements screen has to tell apart.
            bucket = index % 3
            if bucket == 0:
                starts = self.now - timedelta(days=self.rng.randint(30, 120))
                ends = starts + timedelta(days=7)
            elif bucket == 1:
                starts = self.now - timedelta(days=self.rng.randint(1, 5))
                ends = self.now + timedelta(days=self.rng.randint(3, 20))
            else:
                starts = self.now + timedelta(days=self.rng.randint(2, 40))
                ends = None
            rows.append(
                Announcement(
                    title=topic,
                    content=(
                        f"{topic}. Collection windows on the affected days move by one hour; "
                        "check your order before travelling."
                    ),
                    audience=audiences[index % len(audiences)],
                    starts_at=starts,
                    ends_at=ends,
                    is_active=index % 8 != 0,
                    created_by=admin,
                )
            )
        Announcement.objects.bulk_create(rows, batch_size=200)
        self.counts["Announcements"] = len(rows)

    # ---------------------------------------------------------------- closures

    def _seed_closures(self, total, markets, farmers) -> None:
        tradeable = [f for f in farmers if f.status == FarmerStatus.APPROVED]
        market_rows, farmer_rows = [], []
        for index in range(total):
            start, end = self._closure_window(index)
            market_rows.append(
                MarketClosure(
                    market=markets[index % len(markets)],
                    start_date=start,
                    end_date=end,
                    reason=self.rng.choice(
                        ["Public holiday", "Flooding", "Renovation work", "Health inspection"]
                    ),
                )
            )
            if tradeable:
                start, end = self._closure_window(index + 1)
                farmer_rows.append(
                    FarmerClosure(
                        farmer=tradeable[index % len(tradeable)],
                        start_date=start,
                        end_date=end,
                        reason=self.rng.choice(
                            ["Family event", "Crop failure", "Illness", "Away for the harvest"]
                        ),
                    )
                )
        MarketClosure.objects.bulk_create(market_rows, batch_size=200)
        FarmerClosure.objects.bulk_create(farmer_rows, batch_size=200)
        self.counts["Market closures"] = len(market_rows)
        self.counts["Stall closures"] = len(farmer_rows)

    def _closure_window(self, index: int) -> tuple[date, date]:
        """Past, current or upcoming in turn, so every closure state is on screen."""
        span = self.rng.randint(0, 5)
        if index % 3 == 0:
            start = self.today - timedelta(days=self.rng.randint(30, 200))
        elif index % 3 == 1:
            start = self.today - timedelta(days=self.rng.randint(0, span))
        else:
            start = self.today + timedelta(days=self.rng.randint(1, 60))
        return start, start + timedelta(days=span)

    # --------------------------------------------------------------- audit log

    def _seed_audit_logs(self, total, admin, customers, farmers) -> None:
        actors = [admin, *customers[:20], *[f.user for f in farmers[:20]]]
        actions = list(AuditAction.values)
        rows = []
        for index in range(total):
            action = actions[index % len(actions)]
            failed = action in (AuditAction.LOGIN_FAILED, AuditAction.ACCESS_DENIED)
            rows.append(
                AuditLog(
                    # A failed sign-in has no signed-in user, which the screen must render.
                    user=None if action == AuditAction.LOGIN_FAILED else actors[index % len(actors)],
                    action=action,
                    endpoint=f"/api/v1/admin/{action.lower()}/",
                    method=self.rng.choice(["GET", "POST", "PATCH", "DELETE"]),
                    ip_address=f"14.{self.rng.randint(0, 255)}.{self.rng.randint(0, 255)}.{self.rng.randint(1, 254)}",
                    user_agent=self.rng.choice(USER_AGENTS),
                    status_code=self.rng.choice([401, 403]) if failed else self.rng.choice([200, 201, 204]),
                    request_id=f"seed-{index:06d}",
                    details={"seeded": True, "note": AuditAction(action).label},
                )
            )
        AuditLog.objects.bulk_create(rows, batch_size=200)
        self._spread_created_at(AuditLog, len(rows), 90)
        self.counts["Audit log"] = len(rows)

    # -------------------------------------------------------------------- queue

    def _seed_flags(self, total, admin, products) -> None:
        if ModerationFlag.objects.filter(note__in=FLAG_NOTES).count() >= total:
            return
        product_ids = [p.id for p in products]
        stall_review_ids = list(FarmerReview.objects.values_list("id", flat=True)[:total])
        product_review_ids = list(ProductReview.objects.values_list("id", flat=True)[:total])
        farmer_ids = list(
            FarmerProfile.objects.filter(user__email__endswith=f"@{DEMO_DOMAIN}")
            .values_list("user_id", flat=True)[:total]
        )
        customer_ids = list(
            CustomerProfile.objects.filter(user__email__endswith=f"@{DEMO_DOMAIN}")
            .values_list("user_id", flat=True)[:total]
        )
        pools = {
            FlagTarget.PRODUCT: product_ids,
            FlagTarget.FARMER_REVIEW: stall_review_ids,
            FlagTarget.PRODUCT_REVIEW: product_review_ids,
            FlagTarget.FARMER: farmer_ids,
            FlagTarget.CUSTOMER: customer_ids,
        }
        kinds = [kind for kind, pool in pools.items() if pool]
        if not kinds:
            return

        rows = []
        # One open flag per thing is a service rule, so the seed honours it rather than
        # producing a queue the app itself would refuse to create.
        used: set[tuple[str, int]] = set(
            ModerationFlag.objects.filter(resolved_at__isnull=True).values_list(
                "target_type", "target_id"
            )
        )
        index = 0
        while len(rows) < total and index < total * 20:
            kind = kinds[index % len(kinds)]
            index += 1
            pool = pools[kind]
            target_id = pool[self.rng.randrange(len(pool))]
            # Two in five arrive already dealt with, which is the only way the "Already dealt
            # with" filter has anything to show.
            resolved = len(rows) % 5 >= 3
            if not resolved:
                if (kind, target_id) in used:
                    continue
                used.add((kind, target_id))
            rows.append(
                ModerationFlag(
                    target_type=kind,
                    target_id=target_id,
                    note=self.rng.choice(FLAG_NOTES_BY_TARGET[kind]),
                    raised_by=admin,
                    resolved_at=self.now - timedelta(days=self.rng.randint(1, 25))
                    if resolved
                    else None,
                    resolved_by=admin if resolved else None,
                    resolution=FLAG_RESOLUTIONS[len(rows) % len(FLAG_RESOLUTIONS)]
                    if resolved
                    else None,
                )
            )
        ModerationFlag.objects.bulk_create(rows, batch_size=200)
        self._spread_created_at(ModerationFlag, len(rows), 60)
        self.counts["Follow-up queue"] = len(rows)

    # ----------------------------------------------------------------- helpers

    def _spread_created_at(self, model, expected: int, days: int) -> None:
        """Push created_at back over `days`, since auto_now_add stamps every bulk row with now.

        Without this every date filter and every "newest first" sort in the admin sees one
        single timestamp and proves nothing.

        The rows are re-read rather than taken from the bulk_create return value: MySQL cannot
        report the ids it assigned, so those objects come back with pk=None and bulk_update on
        them would raise. The newest `expected` ids are exactly the batch just written.
        """
        if not expected:
            return
        rows = list(model.objects.order_by("-id")[:expected])
        for row in rows:
            row.created_at = self.now - timedelta(
                days=self.rng.randint(0, days),
                hours=self.rng.randint(0, 23),
                minutes=self.rng.randint(0, 59),
            )
        model.objects.bulk_update(rows, ["created_at"], batch_size=200)

    def _report(self) -> None:
        width = max(len(label) for label in self.counts)
        for label, number in self.counts.items():
            self.stdout.write(f"  {label.ljust(width)} : {number}")
