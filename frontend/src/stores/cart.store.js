import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { moneyToNumber } from '../utils/helpers/domain';

/** CU-04 caps a line at 999 and a checkout at 5 farmers, so the cart never builds a body that 400s. */
export const MAX_QUANTITY = 999;
export const MAX_FARMERS_PER_CHECKOUT = 5;

/**
 * The cart (D-004). No API, no server copy: it lives in `localStorage` and is grouped by farmer,
 * because checkout turns each group into its own independent order.
 *
 * Prices kept here are for display only. CU-04 reads the price from the database, so a line that has
 * gone stale can show the wrong subtotal but can never change what the customer is charged — C-01
 * refreshes every line against PU-10 when the page opens.
 */
function clamp(quantity) {
  return Math.min(Math.max(quantity, 0), MAX_QUANTITY);
}

export const useCartStore = create(
  persist(
    (set) => ({
      lines: [],

      addItem: (product, quantity = 1) =>
        set((state) => {
          const existing = state.lines.find((line) => line.product_id === product.product_id);
          if (!existing) {
            return { lines: [...state.lines, { ...product, quantity: clamp(quantity) }] };
          }
          return {
            lines: state.lines.map((line) =>
              (line.product_id === product.product_id
                ? { ...line, ...product, quantity: clamp(line.quantity + quantity) }
                : line)),
          };
        }),

      setQuantity: (productId, quantity) =>
        set((state) => {
          const wanted = clamp(quantity);
          if (wanted === 0) {
            return { lines: state.lines.filter((line) => line.product_id !== productId) };
          }
          return {
            lines: state.lines.map((line) =>
              (line.product_id === productId ? { ...line, quantity: wanted } : line)),
          };
        }),

      removeItem: (productId) =>
        set((state) => ({ lines: state.lines.filter((line) => line.product_id !== productId) })),

      /**
       * Bring every line up to date with PU-10 (`?ids=`). A product the catalogue no longer returns
       * has been archived or removed, which for the customer is the same as unavailable.
       */
      refreshLines: (products) =>
        set((state) => {
          const byId = new Map(products.map((product) => [product.id, product]));
          return {
            lines: state.lines.map((line) => {
              const fresh = byId.get(line.product_id);
              if (!fresh) return { ...line, availability: 'UNAVAILABLE', stock_quantity: 0 };
              return {
                ...line,
                name: fresh.name,
                unit: fresh.unit,
                price: fresh.price,
                image: fresh.image,
                farmer_id: fresh.farmer.id,
                farmer_stall_name: fresh.farmer.stall_name,
                stock_quantity: fresh.stock_quantity,
                availability: fresh.availability,
              };
            }),
          };
        }),

      clear: () => set({ lines: [] }),
    }),
    {
      name: 'marketlink-cart',
      partialize: (state) => ({ lines: state.lines }),
    },
  ),
);

/** A line can be ordered unless the last refresh said otherwise. */
export function isOrderable(line) {
  return line.availability === undefined || line.availability === 'IN_STOCK';
}

/** One block per farmer, in the order the farmers first appeared in the cart. */
export function cartGroups(lines) {
  const groups = [];
  const byFarmer = new Map();

  lines.forEach((line) => {
    let group = byFarmer.get(line.farmer_id);
    if (!group) {
      group = {
        farmer_id: line.farmer_id,
        farmer_stall_name: line.farmer_stall_name,
        lines: [],
        subtotal: 0,
      };
      byFarmer.set(line.farmer_id, group);
      groups.push(group);
    }
    group.lines.push(line);
    if (isOrderable(line)) {
      group.subtotal += moneyToNumber(line.price) * line.quantity;
    }
  });

  return groups;
}

export function cartTotal(lines) {
  return lines.reduce(
    (total, line) => (isOrderable(line) ? total + moneyToNumber(line.price) * line.quantity : total),
    0,
  );
}

export function cartCount(lines) {
  return lines.reduce((count, line) => count + line.quantity, 0);
}
