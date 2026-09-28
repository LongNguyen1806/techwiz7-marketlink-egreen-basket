"""The assistant's tools: read-only lookups over the platform's own selectors (D-011).

No tool writes anything, runs SQL the model wrote, or reveals another user's data. What a tool
may see depends on who is asking:

* everyone (guest included): produce on sale, markets, stalls and their pickup times;
* a customer: also their own orders;
* a farmer: also their own stall (order counts, products needing attention, time off);
* an admin: also the platform's work queue (counts only, no personal data).

Every result is capped (MAX_ROWS) and carries public or own-account fields only.
"""

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from accounts.models import FarmerProfile
from accounts.selectors import farmer_closure_map, farmer_market_rows, pickup_windows, public_farmers
from catalog.ai_review.wordlists import strip_marks
from catalog.models import Category, Product, ReviewStatus
from catalog.selectors import markets_for_products, public_products
from marketlink_core.constants import BOOKING_HORIZON_DAYS
from marketlink_core.policies.roles import RoleCode
from markets.models import FarmerClosure, Market
from markets.selectors import closure_map, public_markets
from orders.models import Order, OrderStatus
from orders.selectors import OPEN_TAB, customer_orders_queryset

logger = logging.getLogger("marketlink")

MAX_ROWS = 5
MAX_OWN_PRODUCTS = 10
LOW_STOCK = 5

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
DAY_NAMES = {index + 1: name.capitalize() for index, name in enumerate(DAYS)}
STATUS_LABEL = {value: label for value, label in OrderStatus.choices}


@dataclass(frozen=True)
class Asker:
    """Who is chatting; decides which tools exist for this conversation."""

    user: object | None
    role: str

    @classmethod
    def from_request(cls, request) -> "Asker":
        user = request.user if getattr(request.user, "is_authenticated", False) else None
        role = getattr(getattr(user, "role", None), "code", None) if user else None
        return cls(user=user, role=role or "GUEST")




def _local(dt) -> str:
    return timezone.localtime(dt).strftime("%d/%m/%Y %H:%M") if dt else ""


def _date(value) -> str:
    return value.strftime("%d/%m/%Y") if value else ""


def _day(value) -> int | None:
    """"saturday" / "Sat" / 6 -> 6; anything else -> None."""
    if isinstance(value, int) and 1 <= value <= 7:
        return value
    text = str(value or "").strip().lower()
    for index, name in enumerate(DAYS, start=1):
        if text and name.startswith(text[:3]):
            return index
    return None


def _variants(args: dict, key: str, single: str | None = None) -> list[str]:
    """Spellings to search: what the model sent, plus each one without Vietnamese marks.

    Names are stored as typed by the stall or admin ("Cho Ben Thanh") and matched accent-
    sensitively, so "Chợ Bến Thành" must also be tried as "cho ben thanh". Added here rather than
    trusted to the model, which does not always send both.
    """
    values = args.get(key) or []
    if isinstance(values, str):
        values = [values]
    if single and args.get(single):
        values = [args[single], *values]
    spelled = [str(value).strip() for value in values if str(value).strip()][:4]
    plain = [strip_marks(value) for value in spelled]
    return list(dict.fromkeys([*spelled, *plain]))[:8]


def _closures(rows) -> list[str]:
    return [
        f"{_date(c.start_date)}-{_date(c.end_date)}" + (f" ({c.reason})" if getattr(c, "reason", None) else "")
        for c in rows
    ]


def _first_match(names: list[str], lookup) -> object | None:
    for name in names:
        found = lookup(name)
        if found is not None:
            return found
    return None




def search_products(asker: Asker, args: dict) -> dict:
    keywords = _variants(args, "keywords", "keyword")
    if not keywords:
        return {"error": "Give at least one keyword."}
    category_id = None
    if args.get("category"):
        category = Category.objects.filter(name__icontains=str(args["category"]).strip(), is_active=True).first()
        category_id = category.pk if category else None
    market_id = None
    if args.get("market"):
        market = _first_match(_variants(args, "market_names", "market"), lambda n: Market.objects.filter(is_active=True, name__icontains=n).first())
        if market is None:
            return {"results": [], "note": f"No market called {args['market']!r}."}
        market_id = market.pk
    day = _day(args.get("day"))

    found: dict[int, Product] = {}
    for keyword in keywords:
        queryset = public_products(q=keyword, category_ids=[category_id] if category_id else None, market_id=market_id, day=day)
        for product in queryset[:MAX_ROWS]:
            found.setdefault(product.pk, product)
        if len(found) >= MAX_ROWS:
            break
    products = list(found.values())[:MAX_ROWS]
    markets = markets_for_products(product_ids=[p.pk for p in products])
    return {
        "results": [
            {
                "name": p.name,
                "price": f"${p.price}",
                "unit": p.unit.lower(),
                "in_stock": p.stock_quantity,
                "stall": p.farmer.stall_name,
                "category": p.category.name,
                "markets": [row["market_name"] for row in markets.get(p.pk, [])],
                "min_per_order": p.min_per_order,
                "max_per_order": p.max_per_order,
            }
            for p in products
        ],
        "note": "Only listings on sale now (approved, in stock). Shoppers order from the Produce page.",
    }


def get_market_info(asker: Asker, args: dict) -> dict:
    names = _variants(args, "names", "name")
    queryset = public_markets(day=_day(args.get("day")))
    markets = []
    for name in names or [""]:
        for market in queryset.filter(Q(name__icontains=name) | Q(address__icontains=name))[:MAX_ROWS]:
            if market.pk not in {m.pk for m in markets}:
                markets.append(market)
    markets = markets[:MAX_ROWS]
    closures = closure_map(market_ids=[m.pk for m in markets])
    return {
        "results": [
            {
                "name": m.name,
                "address": m.address,
                "open_days": [DAY_NAMES[d.day_of_week] for d in m.operating_days.all()],
                "hours": f"{m.open_time:%H:%M}-{m.close_time:%H:%M}",
                "stalls": getattr(m, "farmer_count", None),
                "closed_on": _closures(closures.get(m.pk, [])),
            }
            for m in markets
        ]
    }


def get_farmer_availability(asker: Asker, args: dict) -> dict:
    names = _variants(args, "names", "name")
    farmers = []
    for name in names or [""]:
        for farmer in public_farmers(q=name)[:MAX_ROWS]:
            if farmer.pk not in {f.pk for f in farmers}:
                farmers.append(farmer)
    farmers = farmers[:MAX_ROWS]
    ids = [f.pk for f in farmers]
    markets, closures = farmer_market_rows(farmer_ids=ids), farmer_closure_map(farmer_ids=ids)
    return {
        "results": [
            {
                "stall": f.stall_name,
                "sells_on": [DAY_NAMES[d] for d in sorted(f.operating_days or [])],
                "markets": [f"{row['market_name']} ({row['stall_label']})" for row in markets.get(f.pk, [])],
                "pickup_slots": [
                    f"{window['market_name']}: {DAY_NAMES[slot['day_of_week']]} {slot['start_time']}-{slot['end_time']}"
                    for window in pickup_windows(farmer_id=f.pk)
                    for slot in window["slots"]
                ][:12],
                "order_cutoff_hours_before_pickup": f.order_cutoff_hours,
                "time_off": _closures(closures.get(f.pk, [])),
            }
            for f in farmers
        ],
        "note": f"Orders can be placed up to {BOOKING_HORIZON_DAYS} days ahead.",
    }




def get_my_orders(asker: Asker, args: dict) -> dict:
    if asker.role != RoleCode.CUSTOMER:
        return {"error": "sign_in_required", "note": "Only a signed-in shopper can see their orders."}
    scope = "history" if args.get("scope") == "recent" else "open"
    orders = customer_orders_queryset(asker.user, tab=scope)[:MAX_ROWS]
    return {
        "results": [
            {
                "order": f"#{o.pk}",
                "status": STATUS_LABEL.get(o.status, o.status),
                "stall": o.farmer.stall_name,
                "market": o.market.name,
                "pickup": f"{_local(o.pickup_start_at)}-{timezone.localtime(o.pickup_end_at):%H:%M}",
                "items": o.item_count,
                "total": f"${o.total_amount}",
            }
            for o in orders
        ],
        "note": "Details, changes and cancelling are on the My orders page (before the stall's cut-off).",
    }




def _farmer(asker: Asker):
    return getattr(asker.user, "farmer_profile", None) if asker.role == RoleCode.FARMER else None


def get_my_stall_overview(asker: Asker, args: dict) -> dict:
    profile = _farmer(asker)
    if profile is None:
        return {"error": "farmer_only"}
    orders = Order.objects.filter(farmer=profile)
    today = timezone.localdate()
    by_day = (
        orders.filter(status__in=OPEN_TAB, pickup_date__gte=today)
        .values("pickup_date")
        .annotate(total=Count("id"))
        .order_by("pickup_date")[:7]
    )
    time_off = FarmerClosure.objects.filter(farmer=profile, end_date__gte=today).order_by("start_date")[:3]
    return {
        "stall": profile.stall_name,
        "account_status": profile.status,
        "waiting_for_your_approval": orders.filter(status=OrderStatus.PLACED).count(),
        "accepted": orders.filter(status=OrderStatus.ACCEPTED).count(),
        "ready_for_pickup": orders.filter(status=OrderStatus.READY_FOR_PICKUP).count(),
        "overdue": orders.filter(status__in=(OrderStatus.ACCEPTED, OrderStatus.READY_FOR_PICKUP), pickup_end_at__lt=timezone.now()).count(),
        "change_requests": orders.filter(status=OrderStatus.ACCEPTED, pending_change__isnull=False).count(),
        "open_orders_by_pickup_day": [{"date": _date(row["pickup_date"]), "orders": row["total"]} for row in by_day],
        "time_off": _closures(time_off),
        "note": "Accept, decline and pack orders on the Orders page.",
    }


def get_my_products(asker: Asker, args: dict) -> dict:
    profile = _farmer(asker)
    if profile is None:
        return {"error": "farmer_only"}
    products = Product.objects.filter(farmer=profile, is_archived=False).select_related("category")
    focus = str(args.get("focus") or "attention")
    if focus == "low_stock":
        products = products.filter(stock_quantity__gt=0, stock_quantity__lte=LOW_STOCK)
    elif focus == "out_of_stock":
        products = products.filter(stock_quantity=0)
    elif focus == "in_review":
        products = products.filter(review_status=ReviewStatus.PENDING)
    elif focus == "rejected":
        products = products.filter(review_status=ReviewStatus.REJECTED)
    elif focus == "attention":
        products = products.filter(
            Q(stock_quantity__lte=LOW_STOCK) | ~Q(review_status=ReviewStatus.APPROVED) | Q(is_hidden_by_admin=True)
        )
    return {
        "focus": focus,
        "results": [
            {
                "name": p.name,
                "stock": f"{p.stock_quantity} {p.unit.lower()}",
                "price": f"${p.price}",
                "review": p.review_status,
                "review_note": p.review_note,
                "hidden_by_admin": p.is_hidden_by_admin,
                "open_for_sale": p.is_available,
            }
            for p in products.order_by("stock_quantity", "name")[:MAX_OWN_PRODUCTS]
        ],
        "note": "Edit stock, price and limits on the Products page; a new or renamed listing waits for admin approval.",
    }




def get_admin_overview(asker: Asker, args: dict) -> dict:
    if asker.role != RoleCode.ADMIN:
        return {"error": "admin_only"}
    from catalog.ai_review.stats import ai_review_stats
    from system.dashboard import _needs_attention

    attention = _needs_attention()
    ai = ai_review_stats(days=30)
    week_ago = timezone.now() - timedelta(days=7)
    return {
        "waiting": attention,
        "orders_last_7_days": Order.objects.filter(created_at__gte=week_ago).count(),
        "open_orders": Order.objects.filter(status__in=OPEN_TAB).count(),
        "stalls_by_status": {
            row["status"]: row["total"] for row in FarmerProfile.objects.values("status").annotate(total=Count("pk"))
        },
        "ai_listing_review_30_days": {
            key: ai[key] for key in ("reviewed", "agreement_rate", "caught", "false_alarms", "missed", "open_ai_flags")
        },
        "note": "Counts only. Decisions are made on the Approvals, Follow-up queue and other admin pages.",
    }




def _s(**props):
    """Shorthand for an OBJECT schema."""
    from google.genai import types

    return types.Schema(type=types.Type.OBJECT, properties=props)


def _declarations() -> dict:
    from google.genai import types

    string = types.Schema(type=types.Type.STRING)
    strings = types.Schema(type=types.Type.ARRAY, items=string)
    day = types.Schema(type=types.Type.STRING, enum=list(DAYS))
    fd = types.FunctionDeclaration
    return {
        "search_products": fd(
            name="search_products",
            description=(
                "Find produce on sale now. Send several keywords: the words the user typed AND their English and "
                "Vietnamese equivalents (e.g. ['dưa leo', 'dua leo', 'cucumber'])."
            ),
            parameters=_s(keywords=strings, category=string, market=string, day=day),
        ),
        "get_market_info": fd(
            name="get_market_info",
            description="Opening days, hours, address and closures of markets. Leave names empty to list markets.",
            parameters=_s(names=strings, day=day),
        ),
        "get_farmer_availability": fd(
            name="get_farmer_availability",
            description="A stall's selling days, markets, pickup slots, order cut-off and time off, by stall name.",
            parameters=_s(names=strings),
        ),
        "get_my_orders": fd(
            name="get_my_orders",
            description="The signed-in shopper's own orders: 'open' (default) or 'recent' finished ones.",
            parameters=_s(scope=types.Schema(type=types.Type.STRING, enum=["open", "recent"])),
        ),
        "get_my_stall_overview": fd(
            name="get_my_stall_overview",
            description="The signed-in farmer's own stall: orders waiting, accepted, ready, overdue, change requests, pickups by day, time off.",
            parameters=_s(),
        ),
        "get_my_products": fd(
            name="get_my_products",
            description="The signed-in farmer's own products needing attention (low stock, out of stock, in review, rejected).",
            parameters=_s(focus=types.Schema(type=types.Type.STRING, enum=["attention", "low_stock", "out_of_stock", "in_review", "rejected", "all"])),
        ),
        "get_admin_overview": fd(
            name="get_admin_overview",
            description="For admins: what is waiting (approvals, flags, at-risk customers), order counts and AI listing review figures.",
            parameters=_s(),
        ),
    }


TOOL_FUNCTIONS = {
    "search_products": search_products,
    "get_market_info": get_market_info,
    "get_farmer_availability": get_farmer_availability,
    "get_my_orders": get_my_orders,
    "get_my_stall_overview": get_my_stall_overview,
    "get_my_products": get_my_products,
    "get_admin_overview": get_admin_overview,
}

PUBLIC_TOOLS = ("search_products", "get_market_info", "get_farmer_availability")
TOOLS_BY_ROLE = {
    "GUEST": (*PUBLIC_TOOLS, "get_my_orders"),
    RoleCode.CUSTOMER: (*PUBLIC_TOOLS, "get_my_orders"),
    RoleCode.FARMER: (*PUBLIC_TOOLS, "get_my_stall_overview", "get_my_products"),
    RoleCode.ADMIN: (*PUBLIC_TOOLS, "get_admin_overview"),
}


def tools_for(asker: Asker):
    """The Gemini tool list for this asker's role."""
    from google.genai import types

    declarations = _declarations()
    names = TOOLS_BY_ROLE.get(asker.role, TOOLS_BY_ROLE["GUEST"])
    return [types.Tool(function_declarations=[declarations[name] for name in names])]


def run_tool(asker: Asker, name: str, args: dict | None) -> dict:
    """Run one tool the model asked for, only if this role has it. Never raises."""
    if name not in TOOLS_BY_ROLE.get(asker.role, TOOLS_BY_ROLE["GUEST"]):
        return {"error": "not_available_for_this_account"}
    try:
        return TOOL_FUNCTIONS[name](asker, dict(args or {}))
    except Exception:
        logger.exception("Assistant tool %s failed", name)
        return {"error": "lookup_failed"}
