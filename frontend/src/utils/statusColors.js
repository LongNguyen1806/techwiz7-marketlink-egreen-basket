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
