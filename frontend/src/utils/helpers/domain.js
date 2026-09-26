/** Shared domain helpers previously co-located with types. */

export const OPEN_ORDER_STATUSES = Object.freeze([
  'PLACED',
  'ACCEPTED',
  'READY_FOR_PICKUP',
]);

/** Parse API decimal money string (or number) for display/math. */
export function moneyToNumber(amount) {
  const value = typeof amount === 'string' ? Number(amount) : amount;
  return Number.isFinite(value) ? value : 0;
}

export function productAvailability(
  stock_quantity,
  is_available,
  is_hidden = false,
  is_archived = false,
) {
  if (is_hidden || is_archived || !is_available) return 'UNAVAILABLE';
  if (stock_quantity <= 0) return 'OUT_OF_STOCK';
  return 'IN_STOCK';
}
