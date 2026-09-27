// How a listing's review state reads on screen. One place, because the approvals queue, the
// product list and the filter dropdown all have to call the same state by the same name.
const STATES = {
  PENDING: { label: 'Waiting for review', variant: 'warning' },
  APPROVED: { label: 'Approved', variant: 'success' },
  REJECTED: { label: 'Refused', variant: 'danger' },
};

export const REVIEW_STATE = Object.entries(STATES).map(([value, meta]) => ({
  value,
  label: meta.label,
}));

/** Nothing is drawn for an approved listing: on a shop's product list that is the normal case,
 *  and a badge on every row says nothing while hiding the two that matter. */
export function reviewStateBadge(status) {
  if (status === 'APPROVED') return null;
  return STATES[status] ?? null;
}

export function reviewStateLabel(status) {
  return STATES[status]?.label ?? status;
}
