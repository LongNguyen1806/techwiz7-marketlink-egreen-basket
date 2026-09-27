// One colour per order status, shared by every chart that breaks orders down.
//
// Keyed by status rather than by position in the data. An index-based palette repaints every
// slice as soon as one status is missing from a result, so the same green would mean
// "completed" on the dashboard and "cancelled" on the reports page.
export const ORDER_STATUS_COLORS = {
  COMPLETED: '#15803d',
  PLACED: '#2563eb',
  ACCEPTED: '#0d9488',
  READY_FOR_PICKUP: '#4f46e5',
  CANCELLED: '#64748b',
  DECLINED: '#dc2626',
  NO_SHOW: '#b45309',
  EXPIRED: '#7c3aed',
};

const FALLBACK = '#94a3b8';

export function orderStatusColor(status) {
  return ORDER_STATUS_COLORS[status] ?? FALLBACK;
}
