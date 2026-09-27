import {
  Apple,
  Banana,
  Bean,
  Beef,
  Carrot,
  Cherry,
  Citrus,
  Croissant,
  Drumstick,
  Egg,
  Fish,
  Flame,
  Flower2,
  Grape,
  Ham,
  Leaf,
  LeafyGreen,
  Milk,
  Nut,
  Salad,
  Shell,
  ShoppingBasket,
  Soup,
  Sprout,
  TreePine,
  Vegan,
  Wheat,
} from 'lucide-react';

/**
 * The picture for each icon name a category may store.
 *
 * Every name is also listed in `backend/catalog/icons.py`, which is what refuses an unknown
 * one at the API. The two are kept in step by hand; the picker below only offers names it
 * finds here, so if the backend ever lists one this file lacks, that name simply is not
 * offered rather than turning into a wrong picture on the shopper's home page.
 *
 * No two names share a component. A category's icon is unique in the database, and two names
 * drawing the same picture would put that rule back where it started - which is exactly what
 * the old "pepper" and "flame" pair did. Everything here is something a farm produces.
 */
const ICONS = {
  apple: Apple,
  banana: Banana,
  basket: ShoppingBasket,
  bean: Bean,
  beef: Beef,
  carrot: Carrot,
  cherry: Cherry,
  chilli: Flame,
  citrus: Citrus,
  croissant: Croissant,
  drumstick: Drumstick,
  egg: Egg,
  fish: Fish,
  flower: Flower2,
  grape: Grape,
  ham: Ham,
  leaf: Leaf,
  'leafy-green': LeafyGreen,
  milk: Milk,
  nut: Nut,
  salad: Salad,
  seafood: Shell,
  seedling: Sprout,
  soup: Soup,
  tree: TreePine,
  vegan: Vegan,
  wheat: Wheat,
};

// Names an earlier database may still hold. Two kinds: "pepper" and "flame" were two names
// for one picture, and the rest are pictures of prepared food - pizza, beer, ice cream - that
// were dropped because this is a market for what a farm grows, not a menu.
const LEGACY_ALIASES = {
  pepper: 'chilli',
  flame: 'chilli',
  cake: 'croissant',
  cookie: 'croissant',
  donut: 'croissant',
  sandwich: 'croissant',
  pizza: 'croissant',
  candy: 'nut',
  popcorn: 'wheat',
  dessert: 'milk',
  'ice-cream': 'milk',
  juice: 'citrus',
  beer: 'wheat',
  wine: 'grape',
  cocktail: 'citrus',
  'egg-fried': 'egg',
  utensils: 'basket',
};

function normalise(icon) {
  const key = (icon ?? '').trim().toLowerCase();
  return LEGACY_ALIASES[key] ?? key;
}

export function resolveCategoryIcon(icon) {
  return ICONS[normalise(icon)] ?? Leaf;
}

/** Every icon an admin may choose, in the order the picker shows them. */
export const CATEGORY_ICON_NAMES = Object.keys(ICONS);

/** What to call an icon in a tooltip: "leafy-green" reads better as "Leafy green". */
export function categoryIconLabel(icon) {
  const words = normalise(icon).replaceAll('-', ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}
