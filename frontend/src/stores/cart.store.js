import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { moneyToNumber } from '../utils/helpers/domain';


export const MAX_QUANTITY = 999;
export const MAX_FARMERS_PER_CHECKOUT = 5;


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


export function isOrderable(line) {
  return line.availability === undefined || line.availability === 'IN_STOCK';
}


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
