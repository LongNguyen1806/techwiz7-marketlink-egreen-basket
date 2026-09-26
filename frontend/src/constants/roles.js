export const ROLES = Object.freeze({
  CUSTOMER: 'CUSTOMER',
  FARMER: 'FARMER',
  ADMIN: 'ADMIN',
});

export const FARMER_STATUS = Object.freeze({
  PENDING: 'PENDING',
  APPROVED: 'APPROVED',
  SUSPENDED: 'SUSPENDED',
  REJECTED: 'REJECTED',
});

// The backend refuses writes (FARMER_NOT_APPROVED / FARMER_SUSPENDED) for these statuses.
export const FARMER_WRITE_LOCKED_STATUSES = Object.freeze([
  FARMER_STATUS.PENDING,
  FARMER_STATUS.REJECTED,
  FARMER_STATUS.SUSPENDED,
]);
