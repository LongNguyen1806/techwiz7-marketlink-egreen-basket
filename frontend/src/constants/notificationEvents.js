import { authKeys, farmerKeys, notificationKeys } from './queryKeys';

// Notification types the backend pushes (notifications/models.py NotificationType).
export const NOTIFICATION_TYPES = Object.freeze({
  ORDER_ACCEPTED: 'ORDER_ACCEPTED',
  ORDER_READY: 'ORDER_READY',
  ORDER_DECLINED: 'ORDER_DECLINED',
  ORDER_EXPIRED: 'ORDER_EXPIRED',
  ORDER_CHANGE_APPROVED: 'ORDER_CHANGE_APPROVED',
  ORDER_CHANGE_REJECTED: 'ORDER_CHANGE_REJECTED',
  ORDER_ITEM_SOLD_OUT: 'ORDER_ITEM_SOLD_OUT',
  RESTOCK: 'RESTOCK',
  ORDER_PLACED: 'ORDER_PLACED',
  ORDER_MODIFIED: 'ORDER_MODIFIED',
  ORDER_CANCELLED: 'ORDER_CANCELLED',
  ORDER_CANCELLED_CUSTOMER_LOCKED: 'ORDER_CANCELLED_CUSTOMER_LOCKED',
  ACCOUNT_STATUS_CHANGED: 'ACCOUNT_STATUS_CHANGED',
  MARKET_SCHEDULE_CHANGED: 'MARKET_SCHEDULE_CHANGED',
  MARKET_CLOSED: 'MARKET_CLOSED',
});

const T = NOTIFICATION_TYPES;

// A new or changed order moves counts, lists, stock held by open orders and the dashboard.
const farmerOrderFamily = () => [
  farmerKeys.orders.all(),
  farmerKeys.products.all(),
  farmerKeys.dashboard.all(),
];

// Query families to refresh when a realtime notification of a given type arrives.
// Customer entries are added with the customer branch.
const INVALIDATIONS = {
  [T.ORDER_PLACED]: farmerOrderFamily,
  [T.ORDER_MODIFIED]: farmerOrderFamily,
  [T.ORDER_CANCELLED]: farmerOrderFamily,
  [T.ORDER_CANCELLED_CUSTOMER_LOCKED]: farmerOrderFamily,
  [T.ACCOUNT_STATUS_CHANGED]: () => [authKeys.me(), farmerKeys.profile(), farmerKeys.dashboard.all()],
  [T.MARKET_SCHEDULE_CHANGED]: () => [farmerKeys.markets(), farmerKeys.closures()],
  // Closing a market declines its open orders and switches off its pickup slots.
  [T.MARKET_CLOSED]: () => [farmerKeys.markets(), ...farmerOrderFamily()],
};

export function queryKeysForNotification(type) {
  const extra = INVALIDATIONS[type]?.() ?? [];
  return [notificationKeys.all(), ...extra];
}
