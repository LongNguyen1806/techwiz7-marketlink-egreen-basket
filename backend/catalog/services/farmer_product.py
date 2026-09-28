import io
import logging
import warnings
from pathlib import Path
from typing import Any

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.db.models import Avg, Count, Sum
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError

from accounts.models import FarmerProfile
from catalog.models import Product, ProductMarket
from catalog.services.stock import (
    get_pending_quantities,
    get_weekly_pattern_held_quantities,
)
from favorites.models import FavoriteProduct
from marketlink_core.exceptions import (
    BusinessValidationError,
    ErrorCode,
)
from marketlink_core.history import save_with_history
from markets.models import FarmerMarket, PickupSlot
from notifications.models import NotificationType
from notifications.services import notify
from orders.models import Order, OrderItem, OrderStatus
from orders.services.expiry import expire_overdue_orders
from orders.services.fsm import run_with_retry_if_top_level
from reviews.models import ProductReview

logger = logging.getLogger("marketlink")

MAX_IMAGE_SIZE_BYTES = 2 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
IMAGE_FORMAT_EXTENSIONS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
IMAGE_CONTENT_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
MAX_IMAGE_PIXELS = 6000 * 6000
REENCODE_QUALITY = 85


def _image_error(message: str) -> BusinessValidationError:
    return BusinessValidationError(message, code=ErrorCode.VALIDATION_ERROR, errors={"image": [message]})


def validate_image_upload(file: Any) -> Any:
    """
    NFR-01 / CT-18: check extension, declared MIME type, size, pixel count and the real
    content (Pillow), then return a re-encoded copy to store instead of the upload.

    Re-encoding drops EXIF (a phone photo can carry the GPS position of the farm) and any
    bytes hidden around the picture. The stored extension follows the decoded format; the
    client's filename is never trusted.
    """
    if file is None:
        return None

    extension = Path(getattr(file, "name", "") or "").suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise _image_error("Only JPG, PNG or WEBP images are allowed.")

    content_type = (getattr(file, "content_type", None) or "").lower()
    if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise _image_error("Only JPG, PNG or WEBP images are allowed.")

    size = getattr(file, "size", None)
    if size and size > MAX_IMAGE_SIZE_BYTES:
        raise _image_error("Image file size cannot exceed 2MB.")

    content = file.read()
    file.seek(0)
    image_format, pixels = _probe_image(content)

    if image_format not in IMAGE_FORMAT_EXTENSIONS:
        raise _image_error("Unsupported image format. Allowed: JPG, PNG, WEBP.")
    if pixels > MAX_IMAGE_PIXELS:
        raise _image_error("Image dimensions are too large (at most 36 megapixels).")

    extension = IMAGE_FORMAT_EXTENSIONS[image_format]
    return SimpleUploadedFile(
        f"image{extension}", _reencode(content, image_format), content_type=IMAGE_CONTENT_TYPES[image_format]
    )


def _probe_image(content: bytes) -> tuple[str, int]:
    """Read the format and pixel count from the header only, without decoding the picture."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as probe:
                image_format = (probe.format or "").upper()
                width, height = probe.size
                probe.verify()
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise _image_error("The uploaded file is not a valid image.") from None
    return image_format, width * height


def _reencode(content: bytes, image_format: str) -> bytes:
    """Decode and save again: only the pixels survive, never metadata or appended bytes."""
    try:
        with Image.open(io.BytesIO(content)) as source:
            image = ImageOps.exif_transpose(source)
            output = io.BytesIO()
            if image_format == "JPEG":
                if image.mode not in ("RGB", "L"):
                    image = image.convert("RGB")
                image.save(output, format="JPEG", quality=REENCODE_QUALITY, optimize=True)
            elif image_format == "PNG":
                image.save(output, format="PNG", optimize=True)
            else:
                image.save(output, format="WEBP", quality=REENCODE_QUALITY)
    except (OSError, ValueError, SyntaxError):
        raise _image_error("The uploaded file is not a valid image.") from None
    return output.getvalue()


def notify_restock_for_product(*, product: Product) -> int:
    """
    Sends in-app RESTOCK notification to customers who favorited this product (D-025, A-021).
    Only triggered when product is public and stock moves from 0 to > 0. A listing waiting for
    review is not public, so nobody is told about stock they cannot buy.
    """
    if not product.is_on_sale:
        return 0

    favorites = FavoriteProduct.objects.filter(product=product).select_related("customer")
    farmer_name = (
        getattr(product.farmer, "stall_name", None)
        or getattr(product.farmer, "contact_person", None)
        or "Farmer"
    )

    notified = 0
    for fav in favorites:
        try:
            with transaction.atomic():
                notify(
                    recipient=fav.customer,
                    event_type=NotificationType.RESTOCK,
                    context={
                        "product_id": product.id,
                        "product_name": product.name,
                        "farmer_name": farmer_name,
                    },
                )
        except Exception:  # noqa: BLE001
            logger.exception(
                "RESTOCK notification failed for product %s, customer %s", product.id, fav.customer_id
            )
            continue
        notified += 1

    return notified


def validate_market_ids(*, farmer: FarmerProfile, market_ids: list[int]) -> list[int]:
    chosen = list(dict.fromkeys(market_ids))
    if not chosen:
        raise BusinessValidationError(
            "Choose at least one market.", errors={"market_ids": ["Choose at least one market."]}
        )
    selling = set(FarmerMarket.objects.selling().filter(farmer=farmer).values_list("market_id", flat=True))
    unknown = [market_id for market_id in chosen if market_id not in selling]
    if unknown:
        raise BusinessValidationError(
            "You can only sell at markets that have approved your stall.",
            errors={"market_ids": ["You can only sell at markets that have approved your stall."]},
        )
    return chosen


def set_product_markets(*, product: Product, market_ids: list[int]) -> None:
    """Sell the product at exactly these approved markets and nowhere else."""
    chosen = set(validate_market_ids(farmer=product.farmer, market_ids=market_ids))
    stall_ids = set(
        FarmerMarket.objects.selling()
        .filter(farmer_id=product.farmer_id, market_id__in=chosen)
        .values_list("pk", flat=True)
    )
    ProductMarket.objects.filter(product=product).exclude(farmer_market_id__in=stall_ids).delete()
    existing = set(ProductMarket.objects.filter(product=product).values_list("farmer_market_id", flat=True))
    ProductMarket.objects.bulk_create(
        [ProductMarket(product=product, farmer_market_id=stall_id) for stall_id in sorted(stall_ids - existing)]
    )


def sell_everywhere(*, product: Product) -> None:
    """Default for a listing created without a choice: every market that approved the stall today."""
    market_ids = list(
        FarmerMarket.objects.selling().filter(farmer_id=product.farmer_id).values_list("market_id", flat=True)
    )
    if market_ids:
        set_product_markets(product=product, market_ids=market_ids)


def build_product_metrics(*, farmer: FarmerProfile, product_ids: list[int]) -> dict[str, Any]:
    """Batch data for FarmerProduct (Pass 4B §3.3) so a page costs a fixed number of queries."""
    ids = list(product_ids)
    held_rows = (
        OrderItem.objects.filter(
            product_id__in=ids,
            order__status__in=[OrderStatus.ACCEPTED, OrderStatus.READY_FOR_PICKUP],
        )
        .values("product_id")
        .annotate(total=Sum("quantity"))
    )
    rating_rows = (
        ProductReview.objects.filter(order_item__product_id__in=ids, is_hidden_by_admin=False)
        .values("order_item__product_id")
        .annotate(avg=Avg("rating"), count=Count("id"))
    )
    days_by_market: dict[int, set[int]] = {}
    for slot in PickupSlot.objects.filter(farmer_market__farmer=farmer, is_active=True).values(
        "farmer_market__market_id", "day_of_week"
    ):
        days_by_market.setdefault(slot["farmer_market__market_id"], set()).add(slot["day_of_week"])
    stalls = list(
        FarmerMarket.objects.selling().filter(farmer=farmer).select_related("market").order_by("market__name")
    )
    linked = set(ProductMarket.objects.filter(product_id__in=ids).values_list("product_id", "farmer_market_id"))
    markets = {
        product_id: [
            {
                "market_id": fm.market_id,
                "market_name": fm.market.name,
                "days": sorted(days_by_market.get(fm.market_id, set())),
            }
            for fm in stalls
            if (product_id, fm.pk) in linked
        ]
        for product_id in ids
    }
    return {
        "held": {row["product_id"]: row["total"] for row in held_rows},
        "pending": get_pending_quantities(product_ids=ids),
        "ratings": {
            row["order_item__product_id"]: (round(float(row["avg"]), 1), row["count"]) for row in rating_rows
        },
        "markets": markets,
    }


def preview_weekly_template(*, farmer: FarmerProfile) -> dict[str, Any]:
    """
    FA-17: Lazy sweeps overdue orders and previews weekly template stock calculation (D-008, D-029).
    held_quantity only includes ACCEPTED and READY_FOR_PICKUP orders with pickup_end_at > now.
    overdue_orders is a queryset of Order objects; the view renders them as OrderSummary.
    """
    expire_overdue_orders(farmer_id=farmer.pk)

    products = list(
        Product.objects.filter(farmer=farmer, is_archived=False).select_related("category").order_by("name", "id")
    )
    product_ids = [p.id for p in products]
    market_ids: dict[int, list[int]] = {}
    for product_id, market_id in (
        ProductMarket.objects.filter(product_id__in=product_ids)
        .order_by("farmer_market__market_id")
        .values_list("product_id", "farmer_market__market_id")
    ):
        market_ids.setdefault(product_id, []).append(market_id)

    held_dict = get_weekly_pattern_held_quantities(product_ids=product_ids)
    pending_dict = get_pending_quantities(product_ids=product_ids)
    sold_dict = dict(
        OrderItem.objects.filter(
            order__farmer=farmer,
            order__status=OrderStatus.COMPLETED,
            product_id__in=product_ids,
        )
        .values("product_id")
        .annotate(sold=Sum("quantity"))
        .values_list("product_id", "sold")
    )

    rows = []
    for p in products:
        held = held_dict.get(p.id, 0)
        pending = pending_dict.get(p.id, 0)
        sold = sold_dict.get(p.id, 0)
        tpl = p.weekly_default_quantity
        if tpl is not None:
            new_stock = max(tpl - held, 0)
        else:
            new_stock = p.stock_quantity

        rows.append(
            {
                "product_id": p.id,
                "name": p.name,
                "unit": p.unit,
                "category": {"id": p.category_id, "name": p.category.name},
                "market_ids": market_ids.get(p.id, []),
                "weekly_default_quantity": tpl,
                "held_quantity": held,
                "pending_quantity": pending,
                "sold_quantity": sold,
                "current_stock": p.stock_quantity,
                "new_stock": new_stock,
                "is_available": p.is_available,
            }
        )

    overdue_orders = (
        Order.objects.filter(
            farmer=farmer,
            status__in=[OrderStatus.ACCEPTED, OrderStatus.READY_FOR_PICKUP],
            pickup_end_at__lte=timezone.now(),
        )
        .select_related("customer__customer_profile", "farmer", "market")
        .prefetch_related("items__product")
        .order_by("pickup_end_at", "id")
    )

    return {
        "rows": rows,
        "overdue_orders": overdue_orders,
    }


def apply_weekly_template(*, farmer: FarmerProfile, product_ids: list[int] | None = None) -> dict[str, int]:
    """
    FA-18: Applies weekly stock template with row-locking and triggers restock alerts (D-008, D-025, D-029).
    new_stock = max(weekly_default_quantity - held_quantity, 0).
    product_ids limits it to those products (one row on the Weekly stock page); None means all of them.
    Ids of another farmer's or archived products are skipped.
    Lock order (Pass 4A): 1. lazy sweep (own transactions) -> 2. products of the farmer.
    """
    expire_overdue_orders(farmer_id=farmer.pk)

    def _execute() -> dict[str, int]:
        with transaction.atomic():
            templated = Product.objects.select_for_update(of=("self",)).filter(
                farmer=farmer, is_archived=False, weekly_default_quantity__isnull=False
            )
            if product_ids is not None:
                templated = templated.filter(id__in=product_ids)
            products = list(templated.order_by("id"))
            if not products:
                return {"updated_count": 0, "restock_notified": 0}

            held_dict = get_weekly_pattern_held_quantities(product_ids=[p.id for p in products])
            updated_count = 0
            total_restock_notified = 0
            for p in products:
                old_stock = p.stock_quantity
                new_stock = max(p.weekly_default_quantity - held_dict.get(p.id, 0), 0)
                p.stock_quantity = new_stock
                save_with_history(
                    p,
                    update_fields=["stock_quantity", "updated_at"],
                    reason=f"Weekly template applied (default {p.weekly_default_quantity}, held {held_dict.get(p.id, 0)})",
                )
                updated_count += 1

                if old_stock == 0 and new_stock > 0 and p.is_on_sale:
                    total_restock_notified += notify_restock_for_product(product=p)

        return {"updated_count": updated_count, "restock_notified": total_restock_notified}

    return run_with_retry_if_top_level(_execute)
