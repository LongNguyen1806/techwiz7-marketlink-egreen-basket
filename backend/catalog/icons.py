"""The icons a produce category may wear.

Two rules the rest of the code leans on:

* **A category's icon is unique.** Two categories wearing the same picture is the shopper
  seeing one symbol that means two things, which is worse than no symbol at all. The database
  carries this as a unique index; this list is what makes it satisfiable.
* **The name must be one of these.** Before, an unknown name was silently drawn as a leaf, so
  a typo turned into a wrong picture on the shopper's home page with nothing to notice.

Every name here has a matching picture in `frontend/src/utils/categoryIcon.js`. The two lists
are kept in step by hand; the admin's icon picker only offers names it can actually draw, so
if one ever drifts ahead the extra name simply does not appear rather than becoming a leaf.
"""

CATEGORY_ICONS: tuple[str, ...] = (
    "apple",
    "banana",
    "basket",
    "bean",
    "beef",
    "carrot",
    "cherry",
    "chilli",
    "citrus",
    "croissant",
    "drumstick",
    "egg",
    "fish",
    "flower",
    "grape",
    "ham",
    "leaf",
    "leafy-green",
    "milk",
    "nut",
    "salad",
    "seafood",
    "seedling",
    "soup",
    "tree",
    "vegan",
    "wheat",
)

# Names an earlier database may still hold, so a seeded install can be migrated rather than
# hand-edited. Two kinds live here: "pepper" and "flame" were two names for one picture, which
# is exactly what the uniqueness rule exists to prevent; the rest are pictures of prepared
# food - pizza, beer, ice cream - that were dropped because this is a market for what a farm
# grows, not a menu.
LEGACY_ICON_ALIASES = {
    "pepper": "chilli",
    "flame": "chilli",
    "cake": "croissant",
    "cookie": "croissant",
    "donut": "croissant",
    "sandwich": "croissant",
    "pizza": "croissant",
    "candy": "nut",
    "popcorn": "wheat",
    "dessert": "milk",
    "ice-cream": "milk",
    "juice": "citrus",
    "beer": "wheat",
    "wine": "grape",
    "cocktail": "citrus",
    "egg-fried": "egg",
    "utensils": "basket",
}


def canonical_icon(name: str | None) -> str | None:
    """The stored form of an icon name, or None if it is not one we know.

    An alias may land on a picture another category already wears; that clash is the
    serializer's to report, not this function's, because "unknown" and "taken" are different
    problems and deserve different sentences.
    """
    key = (name or "").strip().lower()
    key = LEGACY_ICON_ALIASES.get(key, key)
    return key if key in CATEGORY_ICONS else None
