from django.db import IntegrityError, transaction

from accounts.models import FarmerProfile, FarmerStatus
from catalog.models import Product, ReviewStatus
from favorites.models import FavoriteFarmer, FavoriteMarket, FavoriteProduct
from markets.models import Market
from marketlink_core.exceptions import ResourceNotFoundError


# TODO(G2 public selector): switch to the Admin branch's shared "publicly visible" selectors once merged.
# Pass 4A: "publicly on sale" = not archived, not hidden by admin, farmer APPROVED. Out of stock still counts,
# so customers can favorite a sold-out product to get the restock alert (D-025).
def _public_farmers():
    return FarmerProfile.objects.filter(status=FarmerStatus.APPROVED)


def _public_products():
    # A listing waiting for review is off the shopper side, favorites included (it returns once approved).
    return Product.objects.filter(
        is_archived=False,
        is_hidden_by_admin=False,
        review_status=ReviewStatus.APPROVED,
        farmer__status=FarmerStatus.APPROVED,
    )


def _public_markets():
    return Market.objects.filter(is_active=True)


# kind -> (favorite model, its target field, targets a customer may favorite)
FAVORITE_KINDS = {
    "farmer": (FavoriteFarmer, "farmer", _public_farmers),
    "product": (FavoriteProduct, "product", _public_products),
    "market": (FavoriteMarket, "market", _public_markets),
}


def _already_saved(model, *, customer, field: str, target_id: int) -> bool:
    return model.objects.filter(customer=customer, **{f"{field}_id": target_id}).exists()


def add_favorite(*, customer, kind: str, target_id: int) -> None:
    """CU-14 / CU-16 / CU-17 POST: idempotent, a second add is still a success (Pass 4B §4.3)."""
    model, field, targets = FAVORITE_KINDS[kind]
    if not targets().filter(pk=target_id).exists():
        raise ResourceNotFoundError()
    if _already_saved(model, customer=customer, field=field, target_id=target_id):
        return
    try:
        with transaction.atomic():
            model.objects.create(customer=customer, **{f"{field}_id": target_id})
    except IntegrityError:
        # A concurrent request saved the same favorite first; the UNIQUE index kept a single row.
        pass


def remove_favorite(*, customer, kind: str, target_id: int) -> None:
    """CU-15 / CU-16 / CU-17 DELETE: idempotent, removing a missing favorite is not an error."""
    model, field, _ = FAVORITE_KINDS[kind]
    model.objects.filter(customer=customer, **{f"{field}_id": target_id}).delete()
