import { useState } from 'react';

import { adminApi } from '@/api/admin/adminApi';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { ApiError } from '@/lib/ApiError';
import { QUERY_KEYS } from '@/config/constants';
import { ConfirmDialog } from '@/components/common/modal/ConfirmDialog';
import { EmptyState } from '@/components/common/feedback/EmptyState';
import { FilterBar } from '@/components/common/table/FilterBar';
import { PageHeader } from '@/components/common/layout/PageHeader';
import { PageSkeleton } from '@/components/common/feedback/PageSkeleton';
import { Badge } from '@/components/common/badges/Badge';
import { Button } from '@/components/common/forms/Button';
import { Textarea } from '@/components/common/forms/Textarea';
import { formatDateTime } from '@/utils/formatters';

import './AdminQueuePage.css';

const TARGET_LABEL = {
  PRODUCT: 'Product',
  FARMER_REVIEW: 'Stall review',
  PRODUCT_REVIEW: 'Product review',
  FARMER: 'Stall',
  CUSTOMER: 'Customer',
};

const QUEUE_FILTERS = [
  {
    name: 'target_type',
    label: 'Kind',
    type: 'select',
    allLabel: 'Everything',
    options: Object.entries(TARGET_LABEL).map(([value, label]) => ({ value, label })),
  },
  {
    name: 'resolved',
    label: 'Status',
    type: 'select',
    allLabel: 'Waiting',
    options: [{ value: 'true', label: 'Already dealt with' }],
  },
];

const RESOLUTION_MIN_LENGTH = 5;

export default function AdminQueuePage() {
  const [filters, setFilters] = useState({});
  const [resolving, setResolving] = useState(null);
  const [resolution, setResolution] = useState('');
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: QUERY_KEYS.ADMIN_FLAGS(filters),
    queryFn: () => adminApi.getFlags(filters),
    staleTime: 0,
    placeholderData: (previous) => previous,
  });

  const resolve = useMutation({
    mutationFn: ({ id, text }) => adminApi.resolveFlag(id, text),
    onSuccess: () => {
      toast.success('Marked as dealt with');
      void queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.ADMIN_FLAGS()[0]] });
      void queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.ADMIN_DASHBOARD[0]] });
      setResolving(null);
    },
    onError: (error) => toast.error(ApiError.fromUnknown(error).friendlyMessage),
  });

  const showingResolved = filters.resolved === 'true';

  return (
    <div className="admin-queue-page">
      <PageHeader
        title="Follow-up queue"
        description="Things an admin marked for a second look. Working through this list replaces reading the whole catalogue."
      />

      <FilterBar
        fields={QUEUE_FILTERS}
        value={filters}
        onChange={setFilters}
        onReset={() => setFilters({})}
      />

      {query.isLoading ? (
        <PageSkeleton />
      ) : !query.data?.results.length ? (
        <EmptyState
          title={showingResolved ? 'Nothing has been dealt with yet' : 'Nothing waiting'}
          description={
            showingResolved
              ? undefined
              : 'Flag a product or a review from the moderation screen and it appears here.'
          }
        />
      ) : (
        <ul className="admin-queue-page__list">
          {query.data.results.map((flag) => (
            <li key={flag.id} className="admin-queue-page__item">
              <div className="admin-queue-page__body">
                <div className="admin-queue-page__head">
                  <Badge variant={flag.resolved_at ? 'secondary' : 'warning'}>
                    {TARGET_LABEL[flag.target_type] ?? flag.target_type} #{flag.target_id}
                  </Badge>
                  <span className="page-primitive__muted-xs">
                    {formatDateTime(flag.created_at)} ·{' '}
                    {flag.raised_by?.email ?? 'System'}
                  </span>
                </div>
                <p className="admin-queue-page__note">{flag.note}</p>
                {flag.resolved_at ? (
                  <p className="page-primitive__muted-sm">
                    Dealt with by {flag.resolved_by?.email ?? 'someone'}:{' '}
                    {flag.resolution}
                  </p>
                ) : null}
              </div>
              {flag.resolved_at ? null : (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setResolving(flag);
                    setResolution('');
                  }}
                >
                  Mark as done
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      <ConfirmDialog
        open={Boolean(resolving)}
        onOpenChange={(open) => {
          if (!open) setResolving(null);
        }}
        title="Mark this as dealt with?"
        description="Say what was done. It stays on the record so the next person can see why the item left the queue."
        confirmLabel="Mark as done"
        loading={resolve.isPending}
        confirmDisabled={resolution.trim().length < RESOLUTION_MIN_LENGTH}
        onConfirm={() => {
          if (!resolving) return;
          resolve.mutate({ id: resolving.id, text: resolution });
        }}
      >
        <Textarea
          className="admin-queue-page__resolution"
          placeholder="What did you do about it?"
          value={resolution}
          onChange={(event) => setResolution(event.target.value)}
        />
      </ConfirmDialog>
    </div>
  );
}
