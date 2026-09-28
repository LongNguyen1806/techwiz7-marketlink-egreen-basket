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

export const CATEGORY_ICON_NAMES = Object.keys(ICONS);

export function categoryIconLabel(icon) {
  const words = normalise(icon).replaceAll('-', ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}
