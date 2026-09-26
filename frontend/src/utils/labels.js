// Backend enums shown as English labels. Raw enum values never reach the UI.

const ORDER_STATUS = {
  PLACED: 'Placed',
  ACCEPTED: 'Accepted',
  READY_FOR_PICKUP: 'Ready for pickup',
  COMPLETED: 'Completed',
  DECLINED: 'Declined',
  CANCELLED: 'Cancelled',
  EXPIRED: 'Expired',
  NO_SHOW: 'No-show',
};

const FARMER_STATUS = {
  PENDING: 'Awaiting approval',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
  SUSPENDED: 'Suspended',
};

const FARMER_STATUS_VARIANT = {
  PENDING: 'warning',
  APPROVED: 'success',
  REJECTED: 'danger',
  SUSPENDED: 'danger',
};

const AUDIENCE = {
  ALL: 'Everyone',
  CUSTOMER: 'Shoppers',
  FARMER: 'Farmers',
};

// catalog/models.py Unit
const UNIT = {
  KG: 'kg',
  BUNCH: 'bunch',
  PIECE: 'piece',
  PACK: 'pack',
};

const REVIEW_TYPE = {
  FARMER: 'Stall review',
  PRODUCT: 'Product review',
};

// markets/models.py DayOfWeek: ISO weekdays, Monday = 1 ... Sunday = 7.
export const DAYS_OF_WEEK = Object.freeze([
  { value: 1, short: 'Mon', long: 'Monday' },
  { value: 2, short: 'Tue', long: 'Tuesday' },
  { value: 3, short: 'Wed', long: 'Wednesday' },
  { value: 4, short: 'Thu', long: 'Thursday' },
  { value: 5, short: 'Fri', long: 'Friday' },
  { value: 6, short: 'Sat', long: 'Saturday' },
  { value: 7, short: 'Sun', long: 'Sunday' },
]);

export const UNIT_OPTIONS = Object.freeze(
  Object.entries(UNIT).map(([value, label]) => ({ value, label })),
);

function humanise(value) {
  if (!value) return '';
  const words = String(value).replaceAll('_', ' ').toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function orderStatusLabel(status) {
  return ORDER_STATUS[status] ?? humanise(status);
}

export function farmerStatusLabel(status) {
  return FARMER_STATUS[status] ?? humanise(status);
}

export function farmerStatusVariant(status) {
  return FARMER_STATUS_VARIANT[status] ?? 'secondary';
}

export function audienceLabel(audience) {
  return AUDIENCE[audience] ?? humanise(audience);
}

export function unitLabel(unit) {
  return UNIT[unit] ?? humanise(unit).toLowerCase();
}

export function reviewTypeLabel(type) {
  return REVIEW_TYPE[type] ?? humanise(type);
}

export function dayOfWeekLabel(day, { short = false } = {}) {
  const entry = DAYS_OF_WEEK.find((d) => d.value === Number(day));
  if (!entry) return '';
  return short ? entry.short : entry.long;
}
