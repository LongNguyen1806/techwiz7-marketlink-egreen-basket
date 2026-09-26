const ACTIONS = {
  LOGIN: { label: 'Signed in', tone: 'neutral' },
  LOGIN_FAILED: { label: 'Failed sign-in', tone: 'warning' },
  LOGOUT: { label: 'Signed out', tone: 'neutral' },
  ACCOUNT_REGISTERED: { label: 'Account registered', tone: 'neutral' },
  PASSWORD_CHANGED: { label: 'Password changed', tone: 'neutral' },
  ACCESS_DENIED: { label: 'Access denied', tone: 'danger' },
  EXPORT_DATA: { label: 'Exported a report', tone: 'neutral' },
  FARMER_APPROVED: { label: 'Approved a stall', tone: 'good' },
  FARMER_REJECTED: { label: 'Rejected a stall', tone: 'warning' },
  FARMER_SUSPENDED: { label: 'Suspended a stall', tone: 'danger' },
  FARMER_REINSTATED: { label: 'Reinstated a stall', tone: 'good' },
  CUSTOMER_DEACTIVATED: { label: 'Locked a customer', tone: 'danger' },
  CUSTOMER_ACTIVATED: { label: 'Unlocked a customer', tone: 'good' },
  PRODUCT_HIDDEN: { label: 'Hid a product', tone: 'warning' },
  PRODUCT_RESTORED: { label: 'Restored a product', tone: 'good' },
  REVIEW_HIDDEN: { label: 'Hid a review', tone: 'warning' },
  REVIEW_RESTORED: { label: 'Restored a review', tone: 'good' },
  MARKET_CREATED: { label: 'Added a market', tone: 'neutral' },
  MARKET_UPDATED: { label: 'Edited a market', tone: 'neutral' },
  MARKET_DEACTIVATED: { label: 'Closed a market', tone: 'warning' },
  MARKET_ACTIVATED: { label: 'Reopened a market', tone: 'good' },
  FARMER_UPDATED: { label: 'Edited stall details', tone: 'neutral' },
  CUSTOMER_UPDATED: { label: 'Edited customer details', tone: 'neutral' },
};

export const AUDIT_ACTION_OPTIONS = Object.entries(ACTIONS)
  .map(([value, meta]) => ({ value, label: meta.label }))
  .sort((a, b) => a.label.localeCompare(b.label));

export function auditActionLabel(action) {
  const known = ACTIONS[action];
  if (known) return known.label;
  const words = (action || '').replaceAll('_', ' ').toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function auditActionTone(action) {
  return ACTIONS[action]?.tone ?? 'neutral';
}

function text(details, key) {
  const value = details[key];
  if (typeof value === 'string' && value.trim()) return value.trim();
  if (typeof value === 'number') return String(value);
  return null;
}

export function auditSubject(log) {
  const d = log.details ?? {};
  const parts = [];

  const market = text(d, 'market_id') ?? text(d, 'name');
  const farmer = text(d, 'farmer_id');
  const customer = text(d, 'customer_id');
  const product = text(d, 'product_id');
  const review = text(d, 'review_id');
  const email = text(d, 'email');

  if (log.action?.startsWith('MARKET_') && market) parts.push(`Market ${market}`);
  const stall = text(d, 'stall_name');
  if (farmer) parts.push(stall ? `${stall} (stall #${farmer})` : `Stall #${farmer}`);
  if (customer) parts.push(`Customer #${customer}`);
  if (product) parts.push(`Product #${product}`);
  if (review) {
    const kind = text(d, 'review_type') === 'FARMER' ? 'Stall review' : 'Product review';
    parts.push(`${kind} #${review}`);
  }
  if (email && !parts.length) parts.push(email);

  if (log.action === 'EXPORT_DATA') {
    const from = text(d, 'from');
    const to = text(d, 'to');
    parts.push(from && to ? `Report ${from} → ${to}` : 'Report');
  }

  const fields = d['changed_fields'];
  if (Array.isArray(fields) && fields.length) {
    parts.push(
      `changed ${fields.map((f) => String(f).replaceAll('_', ' ')).join(', ')}`,
    );
  }

  const affected = text(d, 'affected_orders');
  if (affected && affected !== '0') {
    parts.push(`${affected} order${affected === '1' ? '' : 's'} closed`);
  }

  return parts.join(' · ') || '—';
}

export function auditReason(log) {
  return text(log.details ?? {}, 'reason');
}

export function auditOutcome(log) {
  if (log.status_code === null || log.status_code === undefined) return 'unknown';
  return log.status_code < 400 ? 'ok' : 'refused';
}
