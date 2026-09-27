import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';

import {
  useHideModerationItem,
  useModerationReviews,
  useRestoreModerationReview,
} from '../../hooks/queries/admin/useAdminModeration';

import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { EmptyState } from '@/components/feedback/EmptyState';
import { PageHeader } from '@/components/common/PageHeader';
import { PageSkeleton } from '@/components/feedback/PageSkeleton';
import { RatingStars } from '@/components/common/RatingStars';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { SortSelect } from '@/components/common/SortSelect';
import { FilterBar } from '@/components/common/table/FilterBar';
import { useRaiseFlag } from '../../hooks/queries/admin/useAdminFlags';
import { Textarea } from '@/components/ui/Textarea';

import './AdminModerationPage.css';

// AD-23 and AD-24 both require 5 to 500 characters; refusing shorter text here saves a round
// trip that would come back as a 400.
const REASON_MIN_LENGTH = 5;
const FLAG_NOTE_MIN_LENGTH = 5;

function reviewTarget(review) {
  return review.product
    ? review.product.name
    : `Stall review · Order #${review.order_id}`;
}

const REVIEW_FILTERS = [
  {
    name: 'type',
    label: 'Kind',
    type: 'select',
    allLabel: 'Stall and product',
    options: [
      { value: 'FARMER', label: 'Stall reviews' },
      { value: 'PRODUCT', label: 'Product reviews' },
    ],
  },
  {
    name: 'rating',
    label: 'Rating',
    type: 'select',
    allLabel: 'Any rating',
    options: [1, 2, 3, 4, 5].map((n) => ({
      value: String(n),
      label: `${n} star${n === 1 ? '' : 's'}`,
    })),
  },
  {
    name: 'is_hidden',
    label: 'Visibility',
    type: 'select',
    allLabel: 'Shown and hidden',
    options: [
      { value: 'false', label: 'Shown' },
      { value: 'true', label: 'Hidden' },
    ],
  },
];

const REVIEW_SORT = [
  { value: 'rating', label: 'Lowest rating' },
  { value: '-rating', label: 'Highest rating' },
  { value: 'created_at', label: 'Oldest first' },
];

export default function AdminModerationPage() {
  // The follow-up queue links here with the exact review it wants. Read once into the initial
  // filter state rather than kept in sync: the admin may widen the filter afterwards, and the
  // URL should not keep dragging them back to one row.
  const [params, setParams] = useSearchParams();
  const [pinned] = useState(() => ({
    review_id: params.get('review_id') ?? undefined,
    review_type: params.get('review_type') ?? undefined,
  }));

  const [filters, setFilters] = useState(() =>
    pinned.review_id
      ? { review_id: pinned.review_id, type: pinned.review_type }
      : {},
  );
  const [ordering, setOrdering] = useState(undefined);
  const [hideTarget, setHideTarget] = useState(null);
  const [flagTarget, setFlagTarget] = useState(null);
  const [flagNote, setFlagNote] = useState('');
  const [reason, setReason] = useState('');

  const query = useModerationReviews({ ...filters, ordering });
  const hide = useHideModerationItem();
  const restore = useRestoreModerationReview();
  const raiseFlag = useRaiseFlag();

  const clearPin = () => {
    if (!params.size) return;
    setParams(new URLSearchParams(), { replace: true });
  };

  return (
    <div className="page-primitive__stack-4">
      <PageHeader
        title="Review moderation"
        description="What shoppers wrote about stalls and produce. Hide anything abusive or unrelated; the rating behind it stops counting too."
      />

      {pinned.review_id ? (
        <p className="admin-moderation-page__pin">
          Showing one review, opened from the follow-up queue.
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setFilters({});
              clearPin();
            }}
          >
            Show everything
          </Button>
        </p>
      ) : null}

      <FilterBar
        fields={REVIEW_FILTERS}
        value={filters}
        onChange={setFilters}
        onReset={() => {
          setFilters({});
          clearPin();
        }}
      />
      <SortSelect
        id="review-moderation-sort"
        options={REVIEW_SORT}
        value={ordering}
        onChange={setOrdering}
      />

      <div className="admin-moderation-page__list">
        {query.isLoading ? (
          <PageSkeleton />
        ) : !query.data?.results.length ? (
          <EmptyState title="No reviews match this search" />
        ) : (
          query.data.results.map((r) => (
            <div key={`${r.type}-${r.id}`} className="admin-moderation-page__review-card">
              <div className="admin-moderation-page__review-top">
                <div>
                  <p className="admin-moderation-page__name">{r.customer_display_name}</p>
                  <RatingStars value={r.rating} />
                  <p className="page-primitive__muted-xs">{reviewTarget(r)}</p>
                  <p className="admin-moderation-page__comment">{r.comment}</p>
                  {r.is_hidden_by_admin ? (
                    <Badge variant="danger" className="admin-moderation-page__badge">
                      Hidden: {r.hidden_reason}
                    </Badge>
                  ) : null}
                </div>
                <div className="page-primitive__actions-row">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setFlagTarget({
                        target_type:
                          r.type === 'FARMER' ? 'FARMER_REVIEW' : 'PRODUCT_REVIEW',
                        target_id: r.id,
                        name: reviewTarget(r),
                      });
                      setFlagNote('');
                    }}
                  >
                    Flag
                  </Button>
                  {r.is_hidden_by_admin ? (
                    <Button
                      size="sm"
                      onClick={() => restore.mutate({ id: r.id, reviewType: r.type })}
                    >
                      Restore
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => {
                        setHideTarget({ type: 'review', id: r.id, reviewType: r.type });
                        setReason('');
                      }}
                    >
                      Hide
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <ConfirmDialog
        open={Boolean(hideTarget)}
        onOpenChange={(open) => {
          if (!open) setHideTarget(null);
        }}
        title="Hide this review"
        description="Add a short reason before hiding it from shoppers. Its rating stops counting towards the stall's average."
        destructive
        loading={hide.isPending}
        onConfirm={() => {
          if (!hideTarget || reason.trim().length < REASON_MIN_LENGTH) {
            toast.error(`Reason must be at least ${REASON_MIN_LENGTH} characters`);
            return;
          }
          hide.mutate(
            { ...hideTarget, reason },
            {
              onSuccess: () => {
                setHideTarget(null);
                setReason('');
              },
            },
          );
        }}
      >
        <Textarea
          className="admin-moderation-page__reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </ConfirmDialog>

      <ConfirmDialog
        open={Boolean(flagTarget)}
        onOpenChange={(open) => {
          if (!open) setFlagTarget(null);
        }}
        title={`Flag ${flagTarget?.name ?? 'this'} for follow-up?`}
        description="Use this when something looks wrong but the decision is not yours to make right now. It joins the follow-up queue instead of being hidden."
        confirmLabel="Add to queue"
        loading={raiseFlag.isPending}
        confirmDisabled={flagNote.trim().length < FLAG_NOTE_MIN_LENGTH}
        onConfirm={() => {
          if (!flagTarget) return;
          raiseFlag.mutate(
            {
              target_type: flagTarget.target_type,
              target_id: flagTarget.target_id,
              note: flagNote,
            },
            { onSuccess: () => setFlagTarget(null) },
          );
        }}
      >
        <Textarea
          className="admin-moderation-page__reason"
          placeholder="What should the next person look at?"
          value={flagNote}
          onChange={(event) => setFlagNote(event.target.value)}
        />
      </ConfirmDialog>
    </div>
  );
}
