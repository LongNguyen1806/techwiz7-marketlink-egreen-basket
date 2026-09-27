import { useState } from 'react';

import { useAdminAuditLogs } from '../../hooks/queries/admin/useAdminAuditLogs';
import {
  AUDIT_ACTION_OPTIONS,
  auditActionLabel,
  auditActionTone,
  auditOutcome,
  auditReason,
  auditSubject,
} from '@/utils/auditLabels';
import { EmptyState } from '@/components/common/feedback/EmptyState';
import { PageHeader } from '@/components/common/layout/PageHeader';
import { PageSkeleton } from '@/components/common/feedback/PageSkeleton';
import { Badge } from '@/components/common/badges/Badge';
import { Button } from '@/components/common/forms/Button';
import { Input } from '@/components/common/forms/Input';
import { Label } from '@/components/common/forms/Label';
import { SortableTh } from '@/components/common/table/SortableTh';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/common/drawer/Sheet';
import { formatDateTime } from '@/utils/formatters';

import '@/components/common/table/FilterBar.css';
import './AdminAuditLogsPage.css';

const TONE_VARIANT = {
  neutral: 'secondary',
  good: 'success',
  warning: 'warning',
  danger: 'danger',
};

// The technical columns the A-11 spec lists live in the drawer rather than the table: an
// administrator reads the table to find the event and opens a row only to prove it.
function technicalRows(log) {
  return [
    ['Request', [log.method, log.endpoint].filter(Boolean).join(' ') || '—'],
    ['HTTP status', log.status_code === null ? '—' : String(log.status_code)],
    ['IP address', log.ip_address ?? '—'],
    ['Request ID', log.request_id ?? '—'],
    ['Device', log.user_agent ?? '—'],
    ['Event ID', String(log.id)],
  ];
}

// Keys already spoken for by the summary rows; everything else recorded is still listed, so
// the friendlier wording never hides data from the administrator.
const SUMMARISED_KEYS = new Set([
  'farmer_id',
  'customer_id',
  'product_id',
  'review_id',
  'review_type',
  'market_id',
  'stall_name',
  'name',
  'email',
  'reason',
  'affected_orders',
  // Already spelled out in words by auditSubject; leaving it here too printed ["full_name"].
  'changed_fields',
  'from',
  'to',
  // Shown as its own row below, with the numbers written the way an order is referred to.
  'cancelled_order_ids',
  'cancelled_order_ids_truncated',
]);

function extraDetails(log) {
  return Object.entries(log.details ?? {})
    .filter(([key]) => !SUMMARISED_KEYS.has(key))
    .map(([key, value]) => [
      key.replaceAll('_', ' ').replace(/^./, (c) => c.toUpperCase()),
      Array.isArray(value)
        ? value.map((item) => String(item).replaceAll('_', ' ')).join(', ')
        : typeof value === 'object' && value !== null
          ? JSON.stringify(value)
          : String(value),
    ]);
}

// A takedown cancels other people's orders. The count alone cannot answer a shopper asking
// why theirs disappeared, so the row carries the ids and this prints them.
function cancelledOrders(log) {
  const ids = log.details?.cancelled_order_ids;
  if (!Array.isArray(ids) || !ids.length) return null;
  const listed = ids.map((id) => `#${id}`).join(', ');
  return log.details?.cancelled_order_ids_truncated ? `${listed} and more` : listed;
}

function outcomeText(log) {
  const outcome = auditOutcome(log);
  if (outcome === 'ok') return 'Succeeded';
  if (outcome === 'refused') return 'Blocked';
  return '—';
}

export default function AdminAuditLogsPage() {
  const [action, setAction] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [actor, setActor] = useState(null);
  const [filters, setFilters] = useState({ action: '', from: '', to: '' });
  const [page, setPage] = useState(1);
  const [ordering, setOrdering] = useState(undefined);
  const sortBy = (next) => {
    setOrdering(next);
    setPage(1);
  };
  const [selected, setSelected] = useState(null);

  const query = useAdminAuditLogs({
    action: filters.action || undefined,
    // AD-29 filters the actor by id, so the table hands one over instead of asking the
    // administrator to type an email the API would ignore.
    user_id: actor?.id,
    from: filters.from || undefined,
    to: filters.to || undefined,
    ordering,
    page,
  });

  return (
    <div className="admin-audit-logs-page">
      <PageHeader
        title="System log"
        description="Sign-ins and the moderation decisions staff have made. To see how a single record changed over time, open that record and read its own history."
      />

      <form
        className="page-primitive__actions-row"
        onSubmit={(e) => {
          e.preventDefault();
          setFilters({ action, from, to });
          setPage(1);
        }}
      >
        <div className="admin-audit-logs-page__field">
          <select
            id="audit-event"
            className="page-primitive__select"
            value={action}
            onChange={(e) => setAction(e.target.value)}
          >
            <option value="">All events</option>
            {AUDIT_ACTION_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {/* After the select so it can sit on its border, the way Input floats its label. */}
          <Label className="admin-audit-logs-page__field-label" htmlFor="audit-event">
            Event
          </Label>
        </div>
        <Input
          type="date"
          label="From"
          value={from}
          onChange={(e) => setFrom(e.target.value)}
          className="page-primitive__input-auto"
        />
        <Input
          type="date"
          label="To"
          value={to}
          onChange={(e) => setTo(e.target.value)}
          className="page-primitive__input-auto"
        />
        <Button type="submit" size="sm">
          Apply
        </Button>
        {/* Every filter row in the admin ends with this button, enabled or not, so an admin
            learns one place to look rather than one per screen. */}
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="filter-bar__clear"
          disabled={!action && !from && !to && !actor}
          onClick={() => {
            setAction('');
            setFrom('');
            setTo('');
            setActor(null);
            setFilters({ action: '', from: '', to: '' });
            setPage(1);
          }}
        >
          Clear
        </Button>
      </form>

      {actor ? (
        <p className="admin-audit-logs-page__chip">
          Showing only what <strong>{actor.email}</strong> did
          <Button size="sm" variant="ghost" onClick={() => setActor(null)}>
            Show everyone
          </Button>
        </p>
      ) : null}

      {query.isLoading ? (
        <PageSkeleton />
      ) : !query.data?.results.length ? (
        <EmptyState title="Nothing recorded for this filter" />
      ) : (
        <>
          <div className="page-primitive__table-wrap">
            <table className="page-primitive__table page-primitive__table-min-720">
              <thead className="page-primitive__table-head">
                <tr>
                  <SortableTh column="created_at" current={ordering} onSort={sortBy}>
                    When
                  </SortableTh>
                  <SortableTh column="action" current={ordering} onSort={sortBy}>
                    What happened
                  </SortableTh>
                  <SortableTh column="user" current={ordering} onSort={sortBy}>
                    Who did it
                  </SortableTh>
                  <th className="page-primitive__table-th">Affected</th>
                  <SortableTh column="status_code" current={ordering} onSort={sortBy}>
                    Result
                  </SortableTh>
                  <th className="page-primitive__table-th" />
                </tr>
              </thead>
              <tbody>
                {query.data.results.map((log) => (
                  <tr key={log.id} className="page-primitive__table-row">
                    <td className="page-primitive__table-td">
                      {formatDateTime(log.created_at)}
                    </td>
                    <td className="page-primitive__table-td">
                      <Badge variant={TONE_VARIANT[auditActionTone(log.action)]}>
                        {auditActionLabel(log.action)}
                      </Badge>
                    </td>
                    <td className="page-primitive__table-td">
                      {log.user ? (
                        <button
                          type="button"
                          className="admin-audit-logs-page__actor"
                          onClick={() => {
                            const { id, email } = log.user;
                            setActor({ id, email });
                            setPage(1);
                          }}
                        >
                          {log.user.email}
                        </button>
                      ) : (
                        'Visitor (not signed in)'
                      )}
                    </td>
                    <td className="page-primitive__table-td">{auditSubject(log)}</td>
                    <td className="page-primitive__table-td">{outcomeText(log)}</td>
                    <td className="page-primitive__table-td">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setSelected(log)}
                      >
                        Details
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="admin-audit-logs-page__pagination">
            <span>
              Page {query.data.page}/{query.data.total_pages} · {query.data.count} events
            </span>
            <div className="page-primitive__actions-row">
              <Button
                size="sm"
                variant="outline"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={page >= query.data.total_pages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}

      <Sheet
        open={Boolean(selected)}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        <SheetContent className="page-primitive__sheet-md">
          <SheetHeader>
            <SheetTitle>
              {selected ? auditActionLabel(selected.action) : 'Event'}
            </SheetTitle>
          </SheetHeader>
          {selected ? (
            <div className="admin-audit-logs-page__detail">
              <dl className="admin-audit-logs-page__list">
                <div className="admin-audit-logs-page__pair">
                  <dt>When</dt>
                  <dd>{formatDateTime(selected.created_at)}</dd>
                </div>
                <div className="admin-audit-logs-page__pair">
                  <dt>Who did it</dt>
                  <dd>{selected.user?.email ?? 'Visitor (not signed in)'}</dd>
                </div>
                <div className="admin-audit-logs-page__pair">
                  <dt>Affected</dt>
                  <dd>{auditSubject(selected)}</dd>
                </div>
                {auditReason(selected) ? (
                  <div className="admin-audit-logs-page__pair">
                    <dt>Reason given</dt>
                    <dd>{auditReason(selected)}</dd>
                  </div>
                ) : null}
                {cancelledOrders(selected) ? (
                  <div className="admin-audit-logs-page__pair">
                    <dt>Orders cancelled</dt>
                    <dd>{cancelledOrders(selected)}</dd>
                  </div>
                ) : null}
                <div className="admin-audit-logs-page__pair">
                  <dt>Result</dt>
                  <dd>{outcomeText(selected)}</dd>
                </div>
                {extraDetails(selected).map(([label, value]) => (
                  <div key={label} className="admin-audit-logs-page__pair">
                    <dt>{label}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>

              <details className="admin-audit-logs-page__technical">
                <summary>Technical details (for support)</summary>
                <dl className="admin-audit-logs-page__list">
                  {technicalRows(selected).map(([label, value]) => (
                    <div key={label} className="admin-audit-logs-page__pair">
                      <dt>{label}</dt>
                      <dd className="admin-audit-logs-page__mono">{value}</dd>
                    </div>
                  ))}
                </dl>
              </details>
            </div>
          ) : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}
