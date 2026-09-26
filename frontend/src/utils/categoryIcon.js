import {
  Apple,
  Banana,
  Beef,
  CakeSlice,
  Carrot,
  Cherry,
  Citrus,
  Coffee,
  Croissant,
  Drumstick,
  Egg,
  Fish,
  Flame,
  Grape,
  Leaf,
  Milk,
  Nut,
  Salad,
  ShoppingBasket,
  Soup,
  Wheat,
} from 'lucide-react';

const ICONS = {
  apple: Apple,
  banana: Banana,
  basket: ShoppingBasket,
  beef: Beef,
  cake: CakeSlice,
  carrot: Carrot,
  cherry: Cherry,
  citrus: Citrus,
  coffee: Coffee,
  croissant: Croissant,
  drumstick: Drumstick,
  egg: Egg,
  fish: Fish,
  flame: Flame,
  grape: Grape,
  leaf: Leaf,
  milk: Milk,
  nut: Nut,
  pepper: Flame,
  salad: Salad,
  soup: Soup,
  wheat: Wheat,
};

export function resolveCategoryIcon(icon) {
  return ICONS[(icon ?? '').trim().toLowerCase()] ?? Leaf;
}

/** The names an admin may type into the Icon field, for the help text under it. */
export const CATEGORY_ICON_NAMES = Object.keys(ICONS);
