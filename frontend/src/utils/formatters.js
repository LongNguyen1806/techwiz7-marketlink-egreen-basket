import { formatDistanceToNow } from 'date-fns';
import { enUS } from 'date-fns/locale';

// D-020: money is USD, times are shown in GMT+7 whatever the viewer's own time zone is.
export const APP_TIME_ZONE = 'Asia/Ho_Chi_Minh';

const EMPTY = '—';
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;
const TIME_ONLY = /^\d{2}:\d{2}/;

const moneyFormatter = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });

const partsFormatter = new Intl.DateTimeFormat('en-GB', {
  timeZone: APP_TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});

function toDate(value) {
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  if (typeof value === 'string' || typeof value === 'number') {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  return null;
}

function zonedParts(date) {
  const parts = {};
  for (const part of partsFormatter.formatToParts(date)) parts[part.type] = part.value;
  return parts;
}

export function moneyToNumber(amount) {
  const value = typeof amount === 'string' ? Number(amount) : amount;
  return Number.isFinite(value) ? value : 0;
}

/** "$12.50". The API sends money as decimal strings such as "12.50". */
export function formatMoney(amount) {
  if (amount === null || amount === undefined || amount === '') return EMPTY;
  return moneyFormatter.format(moneyToNumber(amount));
}

/** @deprecated USD is the only currency (D-020). Use formatMoney. */
export const formatVnd = formatMoney;

/** "26/09/2026". A "YYYY-MM-DD" date is formatted as-is, never shifted by a time zone. */
export function formatDate(value) {
  if (!value) return EMPTY;
  if (typeof value === 'string' && DATE_ONLY.test(value)) {
    const [year, month, day] = value.split('-');
    return `${day}/${month}/${year}`;
  }
  const date = toDate(value);
  if (!date) return EMPTY;
  const p = zonedParts(date);
  return `${p.day}/${p.month}/${p.year}`;
}

/** "14:30". Also accepts a bare "14:30" / "14:30:00" time from the API. */
export function formatTime(value) {
  if (!value) return EMPTY;
  if (typeof value === 'string' && TIME_ONLY.test(value)) return value.slice(0, 5);
  const date = toDate(value);
  if (!date) return EMPTY;
  const p = zonedParts(date);
  return `${p.hour}:${p.minute}`;
}

/** "26/09/2026 14:30" */
export function formatDateTime(value) {
  const date = toDate(value);
  if (!date) return EMPTY;
  return `${formatDate(date)} ${formatTime(date)}`;
}

/** "08:00–10:00" */
export function formatTimeRange(start, end) {
  return `${formatTime(start)}–${formatTime(end)}`;
}

/** "26/09/2026 08:00–10:00", or both full date-times when the window spans two days. */
export function formatPickupWindow(start, end) {
  if (!start || !end) return EMPTY;
  if (formatDate(start) === formatDate(end)) {
    return `${formatDate(start)} ${formatTimeRange(start, end)}`;
  }
  return `${formatDateTime(start)} – ${formatDateTime(end)}`;
}

/** "3 minutes ago" */
export function formatRelative(value) {
  const date = toDate(value);
  if (!date) return EMPTY;
  return formatDistanceToNow(date, { addSuffix: true, locale: enUS });
}

/** "YYYY-MM-DD" in GMT+7, for date query parameters such as pickup_date. */
export function toApiDate(value = new Date()) {
  const date = toDate(value);
  if (!date) return '';
  const p = zonedParts(date);
  return `${p.year}-${p.month}-${p.day}`;
}
