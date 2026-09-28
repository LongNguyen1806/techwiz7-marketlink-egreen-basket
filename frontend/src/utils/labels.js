

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


const UNIT = {
  KG: 'kg',
  BUNCH: 'bunch',
  EACH: 'each',
  BAG: 'bag',
  BOX: 'box',
  PACK: 'pack',
};

const UNIT_PLURAL = {
  BUNCH: 'bunches',
  BAG: 'bags',
  BOX: 'boxes',
  PACK: 'packs',
};

const REVIEW_TYPE = {
  FARMER: 'Stall review',
  PRODUCT: 'Product review',
};


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

const ORDER_STATUS_SHORT = { READY_FOR_PICKUP: 'Ready' };

export function orderStatusShortLabel(status) {
  return ORDER_STATUS_SHORT[status] ?? orderStatusLabel(status);
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

export function quantityLabel(quantity, unit) {
  if (unit === 'EACH') return String(quantity);
  if (unit === 'KG') return `${quantity} kg`;
  return `${quantity} ${quantity === 1 ? unitLabel(unit) : UNIT_PLURAL[unit] ?? unitLabel(unit)}`;
}

export function perUnitLabel(unit) {
  return unit === 'EACH' ? 'each' : `per ${unitLabel(unit)}`;
}

export function orderWindowLabel({ min, max, unit }) {
  const parts = [min > 1 ? `Min ${quantityLabel(min, unit)}` : null, max ? `Max ${quantityLabel(max, unit)}` : null];
  return `${parts.filter(Boolean).join(' · ')} per order`;
}

export function reviewTypeLabel(type) {
  return REVIEW_TYPE[type] ?? humanise(type);
}

export function dayOfWeekLabel(day, { short = false } = {}) {
  const entry = DAYS_OF_WEEK.find((d) => d.value === Number(day));
  if (!entry) return '';
  return short ? entry.short : entry.long;
}
