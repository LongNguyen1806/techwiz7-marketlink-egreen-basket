import { useState } from 'react';
import { ExternalLink } from 'lucide-react';
import { FlagTargetCard } from '@/components/admin/FlagTargetCard';

import { adminApi } from '@/api/admin/adminApi';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { ApiError } from '@/lib/ApiError';
import { QUERY_KEYS } from '@/config/constants';
import { EmptyState } from '@/components/feedback/EmptyState';
import { FilterBar } from '@/components/common/table/FilterBar';
import { PageHeader } from '@/components/common/PageHeader';
import { PageSkeleton } from '@/components/feedback/PageSkeleton';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Textarea } from '@/components/ui/Textarea';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/Sheet';
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
  // Same debounced box as every other admin table: FilterBar waits for typing to stop and
  // the query runs with staleTime 0, so a stale page of results can never come back.
  { name: 'q', label: 'Search note or number', type: 'search' },
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
  // Read in a panel over the queue rather than on another screen: leaving the page throws
  // away the search and the filters, and this list is worked through one item at a time.
  const [reviewing, setReviewing] = useState(null);
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
                {/* The reported content itself, and the way to it. Deciding without looking
                    is guesswork, and a number alone means hunting for the row by hand. */}
                {flag.target_preview ? (
                  <p className="admin-queue-page__preview">{flag.target_preview}</p>
                ) : (
                  <p className="admin-queue-page__preview admin-queue-page__preview--gone">
                    The flagged item no longer exists.
                  </p>
                )}
                <Button
                  size="sm"
                  variant="ghost"
                  className="admin-queue-page__link"
                  onClick={() => {
                    setReviewing(flag);
                    setResolution('');
                  }}
                >
                  Open
                </Button>
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
                    setReviewing(flag);
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

      <Sheet open={Boolean(reviewing)} onOpenChange={(open) => !open && setReviewing(null)}>
        <SheetContent className="page-primitive__sheet-md">
          <SheetHeader>
            <SheetTitle>
              {reviewing
                ? `${TARGET_LABEL[reviewing.target_type] ?? reviewing.target_type} #${reviewing.target_id}`
                : 'Flagged item'}
            </SheetTitle>
          </SheetHeader>
          <p className="admin-queue-page__panel-note">{reviewing?.note}</p>
          <FlagTargetCard flag={reviewing} />

          {reviewing?.target_url ? (
            // A new tab, not this one: the queue keeps its search and its filters, and the
            // admin comes back to the panel still open on the same item.
            <a
              className="admin-queue-page__link"
              href={reviewing.target_url}
              target="_blank"
              rel="noreferrer"
            >
              Open the full screen
              <ExternalLink className="page-primitive__icon-sm" />
            </a>
          ) : null}

          {reviewing?.resolved_at ? (
            <p className="page-primitive__muted-sm admin-queue-page__panel-resolved">
              Dealt with by {reviewing.resolved_by?.email ?? 'someone'}:{' '}
              {reviewing.resolution}
            </p>
          ) : (
            // The whole decision happens here. Closing the panel to open a second dialog put
            // the item being judged out of sight at the moment of judging it.
            <form
              className="admin-queue-page__panel-form"
              onSubmit={(event) => {
                event.preventDefault();
                if (!reviewing || resolution.trim().length < RESOLUTION_MIN_LENGTH) return;
                resolve.mutate(
                  { id: reviewing.id, text: resolution },
                  { onSuccess: () => setReviewing(null) },
                );
              }}
            >
              <Textarea
                className="admin-queue-page__resolution"
                placeholder="What did you do about it?"
                value={resolution}
                onChange={(event) => setResolution(event.target.value)}
              />
              <Button
                type="submit"
                loading={resolve.isPending}
                disabled={resolution.trim().length < RESOLUTION_MIN_LENGTH}
              >
                Mark as done
              </Button>
            </form>
          )}
        </SheetContent>
      </Sheet>

    </div>
  );
}
