import { useState } from 'react';
import { toast } from 'sonner';

import {
  useHideModerationItem,
  useModerationProducts,
  useModerationReviews,
  useRestoreModerationProduct,
  useRestoreModerationReview,
} from '../../hooks/queries/admin/useAdminModeration';

import { ConfirmDialog } from '@/components/common/modal/ConfirmDialog';
import { EmptyState } from '@/components/common/feedback/EmptyState';
import { PageHeader } from '@/components/common/layout/PageHeader';
import { PageSkeleton } from '@/components/common/feedback/PageSkeleton';
import { LazyImage } from '@/components/common/cards/LazyImage';
import { RatingStars } from '@/components/common/badges/RatingStars';
import { Badge } from '@/components/common/badges/Badge';
import { Button } from '@/components/common/forms/Button';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/common/layout/Tabs';
import { SortSelect } from '@/components/common/table/SortSelect';
import { FilterBar } from '@/components/common/table/FilterBar';
import { useRaiseFlag } from '../../hooks/queries/admin/useAdminFlags';
import { Textarea } from '@/components/common/forms/Textarea';

import './AdminModerationPage.css';

// AD-21, AD-23 and AD-24 all require 5 to 500 characters; rejecting shorter text here
// saves a round trip that would come back as a 400.
const REASON_MIN_LENGTH = 5;

function reviewTarget(review) {
  return review.product
    ? review.product.name
    : `Stall review · Order #${review.order_id}`;
}

const FLAG_NOTE_MIN_LENGTH = 5;

const PRODUCT_FILTERS = [
  { name: 'q', label: 'Search product or stall', type: 'search' },
  {
    name: 'is_hidden',
    label: 'Visibility',
    type: 'select',
    allLabel: 'Shown and hidden',
    options: [
      { value: 'false', label: 'Shown to shoppers' },
      { value: 'true', label: 'Hidden' },
    ],
  },
];

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

const PRODUCT_SORT = [
  { value: 'name', label: 'Name A–Z' },
  { value: 'stall_name', label: 'Stall A–Z' },
  { value: '-price', label: 'Highest price' },
  { value: '-rating', label: 'Highest rated' },
  { value: 'rating', label: 'Lowest rated' },
  { value: '-is_hidden', label: 'Hidden first' },
];

const REVIEW_SORT = [
  { value: 'rating', label: 'Lowest rating' },
  { value: '-rating', label: 'Highest rating' },
  { value: 'created_at', label: 'Oldest first' },
];

export default function AdminModerationPage() {
  const [hideTarget, setHideTarget] = useState(null);
  const [flagTarget, setFlagTarget] = useState(null);
  const [flagNote, setFlagNote] = useState('');
  const [reason, setReason] = useState('');

  // The two tabs sort independently: they are different lists with different columns.
  const [productOrdering, setProductOrdering] = useState(undefined);
  const [reviewOrdering, setReviewOrdering] = useState(undefined);
  const [productFilters, setProductFilters] = useState({});
  const [reviewFilters, setReviewFilters] = useState({});
  const productsQuery = useModerationProducts({
    ...productFilters,
    ordering: productOrdering,
  });
  const reviewsQuery = useModerationReviews({
    ...reviewFilters,
    ordering: reviewOrdering,
  });
  const hide = useHideModerationItem();
  const raiseFlag = useRaiseFlag();
  const restoreProduct = useRestoreModerationProduct();
  const restoreReview = useRestoreModerationReview();

  return (
    <div className="page-primitive__stack-4">
      <PageHeader
        title="Content moderation"
        description="Hide or restore products and reviews that need review."
      />
      <Tabs defaultValue="products">
        <TabsList>
          <TabsTrigger value="products">Products</TabsTrigger>
          <TabsTrigger value="reviews">Reviews</TabsTrigger>
        </TabsList>
        <TabsContent value="products">
          <FilterBar
            fields={PRODUCT_FILTERS}
            value={productFilters}
            onChange={setProductFilters}
            onReset={() => setProductFilters({})}
          />
          <SortSelect
            id="product-moderation-sort"
            options={PRODUCT_SORT}
            value={productOrdering}
            onChange={setProductOrdering}
          />
          <div className="admin-moderation-page__list">
            {productsQuery.isLoading ? (
              <PageSkeleton />
            ) : !productsQuery.data?.results.length ? (
              <EmptyState title="No products awaiting moderation" />
            ) : (
              productsQuery.data.results.map((p) => (
                <div key={p.id} className="admin-moderation-page__row">
                  <div className="admin-moderation-page__info">
                    <LazyImage
                      src={p.image}
                      alt=""
                      className="admin-moderation-page__thumb"
                    />
                    <div>
                      <p className="admin-moderation-page__name">{p.name}</p>
                      <p className="page-primitive__muted-xs">{p.farmer.stall_name}</p>
                      {p.is_hidden_by_admin ? (
                        <Badge variant="danger" className="admin-moderation-page__badge">
                          Hidden: {p.hidden_reason}
                        </Badge>
                      ) : null}
                    </div>
                  </div>
                  <div className="page-primitive__actions-row">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setFlagTarget({
                          target_type: 'PRODUCT',
                          target_id: p.id,
                          name: p.name,
                        });
                        setFlagNote('');
                      }}
                    >
                      Flag
                    </Button>
                    {p.is_hidden_by_admin ? (
                      <Button size="sm" onClick={() => restoreProduct.mutate(p.id)}>
                        Restore
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => {
                          setHideTarget({ type: 'product', id: p.id });
                          setReason('');
                        }}
                      >
                        Hide
                      </Button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </TabsContent>
        <TabsContent value="reviews">
          <FilterBar
            fields={REVIEW_FILTERS}
            value={reviewFilters}
            onChange={setReviewFilters}
            onReset={() => setReviewFilters({})}
          />
          <SortSelect
            id="review-moderation-sort"
            options={REVIEW_SORT}
            value={reviewOrdering}
            onChange={setReviewOrdering}
          />
          <div className="admin-moderation-page__list">
            {reviewsQuery.isLoading ? (
              <PageSkeleton />
            ) : !reviewsQuery.data?.results.length ? (
              <EmptyState title="No reviews awaiting moderation" />
            ) : (
              reviewsQuery.data.results.map((r) => (
                <div key={r.id} className="admin-moderation-page__review-card">
                  <div className="admin-moderation-page__review-top">
                    <div>
                      <p className="admin-moderation-page__name">
                        {r.customer_display_name}
                      </p>
                      <RatingStars value={r.rating} />
                      <p className="page-primitive__muted-xs">{reviewTarget(r)}</p>
                      <p className="admin-moderation-page__comment">{r.comment}</p>
                      {r.is_hidden_by_admin ? (
                        <Badge variant="danger" className="admin-moderation-page__badge">
                          Hidden: {r.hidden_reason}
                        </Badge>
                      ) : null}
                    </div>
                    {r.is_hidden_by_admin ? (
                      <Button
                        size="sm"
                        onClick={() =>
                          restoreReview.mutate({ id: r.id, reviewType: r.type })
                        }
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
              ))
            )}
          </div>
        </TabsContent>
      </Tabs>

      <ConfirmDialog
        open={Boolean(hideTarget)}
        onOpenChange={(open) => {
          if (!open) setHideTarget(null);
        }}
        title="Hide this content"
        description="Add a short reason before hiding it from shoppers."
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
