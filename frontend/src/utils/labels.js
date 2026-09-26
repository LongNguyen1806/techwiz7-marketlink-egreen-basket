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
