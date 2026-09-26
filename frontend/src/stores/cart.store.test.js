import { beforeEach, describe, expect, it } from 'vitest';
import { useCartStore, cartGroups, cartTotal } from './cart.store';

/**
 * D-004: the cart has no API. It lives in localStorage and is grouped by farmer, because checkout
 * turns each group into its own order. Prices held here are for display only — CU-04 reads the
 * price from the database, so a stale line can never change what is charged.
 */
const LETTUCE = {
  product_id: 4, farmer_id: 9, farmer_stall_name: 'Green Stall',
  name: 'Da Lat lettuce', unit: 'kg', price: '12.50', image: null,
};
const TOMATO = {
  product_id: 5, farmer_id: 9, farmer_stall_name: 'Green Stall',
  name: 'Tomato', unit: 'kg', price: '3.00', image: null,
};
const MANGO = {
  product_id: 7, farmer_id: 11, farmer_stall_name: 'Sunny Orchard',
  name: 'Mango', unit: 'kg', price: '8.25', image: null,
};

beforeEach(() => {
  useCartStore.getState().clear();
});

describe('adding', () => {
  it('keeps one line per product and adds up the quantity', () => {
    const { addItem } = useCartStore.getState();

    addItem(LETTUCE, 2);
    addItem(LETTUCE, 3);

    expect(useCartStore.getState().lines).toEqual([{ ...LETTUCE, quantity: 5 }]);
  });

  it('never asks for more than CU-04 accepts', () => {
    const { addItem } = useCartStore.getState();

    addItem(LETTUCE, 998);
    addItem(LETTUCE, 5);

    // The serializer caps quantity at 999, so the cart refuses to build a body that would 400.
    expect(useCartStore.getState().lines[0].quantity).toBe(999);
  });

  it('defaults to one unit', () => {
    useCartStore.getState().addItem(LETTUCE);

    expect(useCartStore.getState().lines[0].quantity).toBe(1);
  });
});

describe('changing a line', () => {
  it('sets an exact quantity', () => {
    useCartStore.getState().addItem(LETTUCE, 2);

    useCartStore.getState().setQuantity(LETTUCE.product_id, 7);

    expect(useCartStore.getState().lines[0].quantity).toBe(7);
  });

  it('drops the line when the quantity reaches zero', () => {
    useCartStore.getState().addItem(LETTUCE, 2);

    useCartStore.getState().setQuantity(LETTUCE.product_id, 0);

    expect(useCartStore.getState().lines).toEqual([]);
  });

  it('removes a line outright', () => {
    const { addItem, removeItem } = useCartStore.getState();
    addItem(LETTUCE, 1);
    addItem(MANGO, 1);

    removeItem(LETTUCE.product_id);

    expect(useCartStore.getState().lines.map((line) => line.product_id)).toEqual([MANGO.product_id]);
  });

  it('refreshes the price and the stall name from the catalogue, keeping the quantity', () => {
    useCartStore.getState().addItem(LETTUCE, 4);

    useCartStore.getState().refreshLines([
      {
        id: 4, name: 'Da Lat lettuce', price: '13.00', unit: 'kg', image: null,
        stock_quantity: 3, availability: 'IN_STOCK', farmer: { id: 9, stall_name: 'Green Stall II' },
      },
    ]);

    const [line] = useCartStore.getState().lines;
    expect(line.price).toBe('13.00');
    expect(line.farmer_stall_name).toBe('Green Stall II');
    expect(line.quantity).toBe(4);
    // PU-08 is what decides a pickup; the cart only needs to know how much is left to warn about.
    expect(line.stock_quantity).toBe(3);
    expect(line.availability).toBe('IN_STOCK');
  });

  it('marks a line the catalogue no longer returns as unavailable', () => {
    useCartStore.getState().addItem(LETTUCE, 4);

    // PU-10 with ids omits archived and removed products entirely.
    useCartStore.getState().refreshLines([]);

    expect(useCartStore.getState().lines[0].availability).toBe('UNAVAILABLE');
  });
});

describe('grouping for checkout', () => {
  it('puts each farmer in its own group, in the order the lines were added', () => {
    const { addItem } = useCartStore.getState();
    addItem(LETTUCE, 1);
    addItem(MANGO, 2);
    addItem(TOMATO, 3);

    const groups = cartGroups(useCartStore.getState().lines);

    expect(groups.map((group) => group.farmer_id)).toEqual([9, 11]);
    expect(groups[0].farmer_stall_name).toBe('Green Stall');
    expect(groups[0].lines.map((line) => line.product_id)).toEqual([4, 5]);
    expect(groups[1].lines).toHaveLength(1);
  });

  it('sums each group and the whole cart from the decimal strings', () => {
    const { addItem } = useCartStore.getState();
    addItem(LETTUCE, 2); // 25.00
    addItem(MANGO, 4); // 33.00

    const groups = cartGroups(useCartStore.getState().lines);

    expect(groups[0].subtotal).toBe(25);
    expect(groups[1].subtotal).toBe(33);
    expect(cartTotal(useCartStore.getState().lines)).toBe(58);
  });

  it('leaves unavailable lines out of the totals', () => {
    const { addItem } = useCartStore.getState();
    addItem(LETTUCE, 2);
    addItem(MANGO, 1);
    useCartStore.getState().refreshLines([
      {
        id: 7, name: 'Mango', price: '8.25', unit: 'kg', image: null,
        stock_quantity: 0, availability: 'OUT_OF_STOCK', farmer: { id: 11, stall_name: 'Sunny Orchard' },
      },
    ]);

    // Lettuce vanished from the catalogue, mango sold out: neither can be ordered right now.
    expect(cartTotal(useCartStore.getState().lines)).toBe(0);
  });
});

describe('persistence', () => {
  it('survives a reload, because a cart is never sent to the server (D-004)', () => {
    useCartStore.getState().addItem(LETTUCE, 2);

    expect(JSON.parse(localStorage.getItem('marketlink-cart')).state.lines)
      .toEqual([{ ...LETTUCE, quantity: 2 }]);
  });
});
