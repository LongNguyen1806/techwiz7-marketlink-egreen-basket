// One place for every enum the API sends and a person has to read. Screens import from here
// instead of printing the raw value, which is how READY_FOR_PICKUP ended up on a chart legend.

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

const AUDIENCE = {
  ALL: 'Everyone',
  CUSTOMER: 'Shoppers',
  FARMER: 'Farmers',
};

// Each lookup falls back to sentence-cased words: an enum value added on the API side later
// still reads as English here rather than as SHOUTING_SNAKE.
function humanise(value) {
  const words = value.replaceAll('_', ' ').toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function orderStatusLabel(status) {
  return ORDER_STATUS[status] ?? humanise(status);
}

// Only "Ready for pickup" is long enough to matter, and in a chart legend beside a number and
// a percentage it was the one getting cut off mid-word.
const ORDER_STATUS_SHORT = { READY_FOR_PICKUP: 'Ready' };

export function orderStatusShortLabel(status) {
  return ORDER_STATUS_SHORT[status] ?? orderStatusLabel(status);
}

export function farmerStatusLabel(status) {
  return FARMER_STATUS[status] ?? humanise(status);
}

// A stall that is suspended or rejected must not wear the same green as an approved one -
// the colour is what an admin reads first when scanning the list.
const FARMER_STATUS_VARIANT = {
  PENDING: 'warning',
  APPROVED: 'success',
  REJECTED: 'danger',
  SUSPENDED: 'danger',
};

export function farmerStatusVariant(status) {
  return FARMER_STATUS_VARIANT[status] ?? 'secondary';
}

export function audienceLabel(audience) {
  return AUDIENCE[audience] ?? humanise(audience);
}
