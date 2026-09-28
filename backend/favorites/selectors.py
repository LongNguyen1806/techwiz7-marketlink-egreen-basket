from accounts.models import CustomUser
from favorites.models import FavoriteFarmer, FavoriteMarket, FavoriteProduct
from marketlink_core.policies.roles import RoleCode

MODELS = {
    "market": (FavoriteMarket, "market_id"),
    "farmer": (FavoriteFarmer, "farmer_id"),
    "product": (FavoriteProduct, "product_id"),
}


def favorite_ids(*, user, kind: str, object_ids) -> set[int] | None:
    """Which of `object_ids` this viewer has hearted, for the is_favorite flag on public lists."""
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    if getattr(getattr(user, "role", None), "code", None) != RoleCode.CUSTOMER:
        return None
    model, column = MODELS[kind]
    return set(
        model.objects.filter(customer=user, **{f"{column}__in": set(object_ids)}).values_list(
            column, flat=True
        )
    )


def customer_favorite_ids(customer) -> dict[str, list[int]]:
    """CU-12: every id the customer has hearted, so the frontend can fill each heart icon."""
    return {
        "farmer_ids": list(FavoriteFarmer.objects.filter(customer=customer).values_list("farmer_id", flat=True)),
        "product_ids": list(FavoriteProduct.objects.filter(customer=customer).values_list("product_id", flat=True)),
        "market_ids": list(FavoriteMarket.objects.filter(customer=customer).values_list("market_id", flat=True)),
    }


def get_restock_subscribers(product_id: int):
    """Customers to notify with RESTOCK when a Farmer restocks the product from 0 (FA-14, FA-18 — D-025, §5.5).

    Locked accounts are skipped. Returns a CustomUser queryset; pass each one to notify(recipient=...).
    """
    return CustomUser.objects.filter(
        favorite_products__product_id=product_id, is_active=True
    ).order_by("pk")
