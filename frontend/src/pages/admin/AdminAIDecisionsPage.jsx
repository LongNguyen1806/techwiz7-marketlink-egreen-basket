import { useState } from 'react';
import { Link } from 'react-router-dom';

import {
  useAIDecisions,
  useCheckAIDecision,
  useOverrideAIDecision,
} from '../../hooks/queries/admin/useAdminAIDecisions';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { FilterBar } from '../../components/common/table/FilterBar';
import { PageHeader } from '../../components/common/PageHeader';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Textarea } from '../../components/ui/Textarea';
import { formatDateTime } from '../../utils/formatters';
import '../../styles/admin/AdminAIDecisionsPage.css';

const REASON_MIN_LENGTH = 5;

const FILTERS = [
  { name: 'q', label: 'Search product or stall', type: 'search' },
  {
    name: 'action',
    label: 'Decision',
    type: 'select',
    allLabel: 'Approved and held',
    options: [
      { value: 'APPROVED', label: 'Approved by AI' },
      { value: 'HELD', label: 'Held by AI' },
    ],
  },
  {
    name: 'checked',
    label: 'Checked',
    type: 'select',
    allLabel: 'Not checked yet',
    options: [
      { value: 'true', label: 'Checked' },
      { value: 'all', label: 'Everything' },
    ],
  },
];

const ACTION = {
  APPROVED: { label: 'Approved by AI', variant: 'success' },
  HELD: { label: 'Held by AI', variant: 'destructive' },
};

export default function AdminAIDecisionsPage() {
  const [filters, setFilters] = useState({});
  const [page, setPage] = useState(1);
  const [undoing, setUndoing] = useState(null);
  const [reason, setReason] = useState('');

  const query = useAIDecisions({ ...filters, page, page_size: 20 });
  const check = useCheckAIDecision();
  const override = useOverrideAIDecision();
  const rows = query.data?.results ?? [];

  const undo = (row) => {
    if (row.auto_action === 'HELD') {
      override.mutate({ productId: row.product.id, approve: true });
      return;
    }
    setReason('');
    setUndoing(row);
  };

  return (
    <div className="admin-ai-decisions">
      <PageHeader
        title="AI decisions"
        description="Listings the AI approved or held on its own. Check each one, or undo it."
      />

      <FilterBar
        fields={FILTERS}
        value={filters}
        onChange={(next) => {
          setFilters(next);
          setPage(1);
        }}
        onReset={() => {
          setFilters({});
          setPage(1);
        }}
      />

      {query.isLoading ? (
        <PageSkeleton />
      ) : rows.length === 0 ? (
        <EmptyState
          title="Nothing to check"
          description="When the AI approves or holds a listing by itself, it shows up here."
        />
      ) : (
        <>
          <ul className="admin-ai-decisions__list">
            {rows.map((row) => {
              const action = ACTION[row.auto_action] ?? ACTION.APPROVED;
              return (
                <li key={row.id} className="admin-ai-decisions__row">
                  {row.product.image ? (
                    <img className="admin-ai-decisions__thumb" src={row.product.image} alt="" />
                  ) : (
                    <div className="admin-ai-decisions__thumb admin-ai-decisions__thumb--empty" />
                  )}
                  <div className="admin-ai-decisions__main">
                    <div className="admin-ai-decisions__head">
                      <strong>{row.product.name}</strong>
                      <Badge variant={action.variant}>{action.label}</Badge>
                      {row.admin_checked_at ? <Badge variant="secondary">Checked</Badge> : null}
                    </div>
                    <p className="page-primitive__muted-sm">
                      <Link to={`/admin/farmers/${row.product.farmer_id}`}>{row.product.stall_name}</Link>
                      {row.product.category ? ` · ${row.product.category}` : ''} ·{' '}
                      {formatDateTime(row.auto_action_at)} · risk {row.risk_score}
                    </p>
                    <p className="admin-ai-decisions__summary">{row.summary}</p>
                    {row.findings?.length ? (
                      <ul className="admin-ai-decisions__findings">
                        {row.findings.slice(0, 3).map((finding, index) => (
                          <li key={index}>
                            <span className="admin-ai-decisions__severity">{finding.severity}</span>{' '}
                            {finding.message}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    {row.admin_checked_at ? (
                      <p className="page-primitive__muted-xs">
                        Checked {formatDateTime(row.admin_checked_at)}
                        {row.checked_by ? ` by ${row.checked_by}` : ''}
                      </p>
                    ) : null}
                  </div>
                  {!row.admin_checked_at ? (
                    <div className="admin-ai-decisions__actions">
                      <Button size="sm" loading={check.isPending} onClick={() => check.mutate(row.id)}>
                        Looks right
                      </Button>
                      <Button
                        size="sm"
                        variant={row.auto_action === 'APPROVED' ? 'destructive' : 'outline'}
                        loading={override.isPending}
                        onClick={() => undo(row)}
                      >
                        {row.auto_action === 'APPROVED' ? 'Take off sale' : 'Approve anyway'}
                      </Button>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>

          <div className="admin-ai-decisions__pagination">
            <span>
              Page {query.data.page}/{query.data.total_pages} · {query.data.count} decisions
            </span>
            <div className="page-primitive__actions-row">
              <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
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

      <ConfirmDialog
        open={Boolean(undoing)}
        onOpenChange={(open) => {
          if (!open) setUndoing(null);
        }}
        title={`Take ${undoing?.product.name ?? 'this listing'} off sale?`}
        description="The stall is told why, so it can fix the listing and send it again."
        confirmLabel="Take off sale"
        destructive
        loading={override.isPending}
        confirmDisabled={reason.trim().length < REASON_MIN_LENGTH}
        onConfirm={() => {
          if (!undoing) return;
          override.mutate(
            { productId: undoing.product.id, approve: false, reason: reason.trim() },
            { onSuccess: () => setUndoing(null) },
          );
        }}
      >
        <Textarea
          placeholder="What is wrong with it? The stall reads this."
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </ConfirmDialog>
    </div>
  );
}
