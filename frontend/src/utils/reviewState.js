const STATES = {
  PENDING: { label: 'Waiting for review', variant: 'warning' },
  APPROVED: { label: 'Approved', variant: 'success' },
  REJECTED: { label: 'Refused', variant: 'danger' },
};

export const REVIEW_STATE = Object.entries(STATES).map(([value, meta]) => ({
  value,
  label: meta.label,
}));

export function reviewStateBadge(status) {
  if (status === 'APPROVED') return null;
  return STATES[status] ?? null;
}

export function reviewStateLabel(status) {
  return STATES[status]?.label ?? status;
}
