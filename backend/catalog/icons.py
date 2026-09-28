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
    "almond",
    "apple",
    "asparagus",
    "avocado",
    "bamboo",
    "banana",
    "basket",
    "bean",
    "beef",
    "beet",
    "bell-pepper",
    "broccoli",
    "butter",
    "cabbage",
    "cactus",
    "carrot",
    "cattle",
    "cheese",
    "cherry",
    "chilli",
    "citrus",
    "coconut",
    "coffee",
    "corn",
    "crab",
    "croissant",
    "drumstick",
    "duck",
    "egg",
    "fish",
    "flower",
    "fruit-bowl",
    "fruit-tree",
    "garlic",
    "goat",
    "grape",
    "ham",
    "herbs",
    "honey",
    "honeycomb",
    "hops",
    "kiwi",
    "leaf",
    "leafy-green",
    "leek",
    "lemon",
    "lotus",
    "milk",
    "mushroom",
    "nut",
    "oat",
    "olive",
    "orange",
    "oyster",
    "palm",
    "peach",
    "peanut",
    "pear",
    "peas",
    "pig",
    "pineapple",
    "potato",
    "potted-plant",
    "poultry",
    "pumpkin",
    "quail-eggs",
    "rabbit",
    "raspberry",
    "rice",
    "salad",
    "seafood",
    "seedling",
    "seeds",
    "sesame",
    "sheep",
    "shrimp",
    "soup",
    "squid",
    "strawberry",
    "sugar-cane",
    "sunflower",
    "tomato",
    "tree",
    "vegan",
    "vine-leaf",
    "watermelon",
    "wheat",
)

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
