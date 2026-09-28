import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';

import {
  useBlockModerationProduct,
  useHideModerationItem,
  useModerationProducts,
  useModerationReviews,
  useRestoreModerationProduct,
  useRestoreModerationReview,
  useUnblockModerationProduct,
} from '../../hooks/queries/admin/useAdminModeration';
import { adminApi } from '@/api/admin/adminApi';

import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { EmptyState } from '@/components/feedback/EmptyState';
import { PageHeader } from '@/components/common/PageHeader';
import { PageSkeleton } from '@/components/feedback/PageSkeleton';
import { LazyImage } from '@/components/common/LazyImage';
import { RatingStars } from '@/components/common/RatingStars';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/Tabs';
import { SortSelect } from '@/components/common/SortSelect';
import { FilterBar } from '@/components/common/table/FilterBar';
import { Textarea } from '@/components/ui/Textarea';

import './AdminModerationPage.css';

const REASON_MIN_LENGTH = 5;

function reviewTarget(review) {
  return review.product
    ? review.product.name
    : `Stall review · Order #${review.order_id}`;
}


const MODERATION_COPY = {
  HIDE: { label: 'Hidden', undo: 'Restore' },
  BLOCK: { label: 'Taken down', undo: 'Unblock' },
};

function moderationCopy(product) {
  return MODERATION_COPY[product.moderation_action] ?? MODERATION_COPY.HIDE;
}

const PRODUCT_FILTERS = [
  { name: 'q', label: 'Search product or stall', type: 'search' },
  {
    name: 'is_hidden',
    label: 'Visibility',
    type: 'select',
    allLabel: 'Shown and hidden',
    options: [
      { value: 'false', label: 'Shown to shoppers' },
      { value: 'true', label: 'Hidden or taken down' },
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
  const [params, setParams] = useSearchParams();
  const [pinned] = useState(() => ({
    tab: params.get('tab') === 'reviews' ? 'reviews' : 'products',
    product_id: params.get('product_id') ?? undefined,
    review_id: params.get('review_id') ?? undefined,
    review_type: params.get('review_type') ?? undefined,
  }));

  const [hideTarget, setHideTarget] = useState(null);
  const [blockTarget, setBlockTarget] = useState(null);
  const [blockImpact, setBlockImpact] = useState('');
  const [unblockTarget, setUnblockTarget] = useState(null);
  const [reason, setReason] = useState('');

  const [productOrdering, setProductOrdering] = useState(undefined);
  const [reviewOrdering, setReviewOrdering] = useState(undefined);
  const [productFilters, setProductFilters] = useState(() =>
    pinned.product_id ? { product_id: pinned.product_id } : {},
  );
  const [reviewFilters, setReviewFilters] = useState(() =>
    pinned.review_id
      ? { review_id: pinned.review_id, type: pinned.review_type }
      : {},
  );

  const clearPin = () => {
    if (!params.size) return;
    setParams(new URLSearchParams(), { replace: true });
  };
  const productsQuery = useModerationProducts({
    ...productFilters,
    ordering: productOrdering,
  });
  const reviewsQuery = useModerationReviews({
    ...reviewFilters,
    ordering: reviewOrdering,
  });
  const hide = useHideModerationItem();
  const block = useBlockModerationProduct();
  const unblock = useUnblockModerationProduct();
  const restoreProduct = useRestoreModerationProduct();
  const restoreReview = useRestoreModerationReview();

  const openBlockDialog = async (product) => {
    setBlockTarget(product);
    setReason('');
    setBlockImpact('');
    try {
      const impact = await adminApi.fetchProductBlockImpact(product.id);
      const held = impact.open_orders.ACCEPTED + impact.open_orders.READY_FOR_PICKUP;
      setBlockImpact(
        `${impact.open_orders.total} open ${
          impact.open_orders.total === 1 ? 'order' : 'orders'
        } from ${impact.affected_customers} ${
          impact.affected_customers === 1 ? 'shopper' : 'shoppers'
        } will be cancelled in full, and the stock of the ${held} already accepted goes back on the shelf.`,
      );
    } catch {
      setBlockImpact('The number of affected orders could not be loaded.');
    }
  };

  return (
    <div className="page-primitive__stack-4">
      <PageHeader
        title="Content moderation"
        description="Hide or restore products and reviews that need review."
      />
      {pinned.product_id || pinned.review_id ? (
        <p className="admin-moderation-page__pin">
          Showing one item, opened from the follow-up queue.
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setProductFilters({});
              setReviewFilters({});
              clearPin();
            }}
          >
            Show everything
          </Button>
        </p>
      ) : null}
      <Tabs defaultValue={pinned.tab}>
        <TabsList>
          <TabsTrigger value="products">Products</TabsTrigger>
          <TabsTrigger value="reviews">Reviews</TabsTrigger>
        </TabsList>
        <TabsContent value="products">
          <FilterBar
            fields={PRODUCT_FILTERS}
            value={productFilters}
            onChange={setProductFilters}
            onReset={() => {
              setProductFilters({});
              clearPin();
            }}
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
                      <p className="page-primitive__muted-xs">
                        {p.farmer.stall_name}
                        {p.open_order_count ? (
                          <>
                            {' · '}
                            {p.open_order_count} open{' '}
                            {p.open_order_count === 1 ? 'order' : 'orders'}
                          </>
                        ) : null}
                      </p>
                      {p.is_hidden_by_admin ? (
                        <Badge variant="danger" className="admin-moderation-page__badge">
                          {moderationCopy(p).label}: {p.hidden_reason}
                        </Badge>
                      ) : null}
                    </div>
                  </div>
                  <div className="page-primitive__actions-row">
                    {p.moderation_action === 'BLOCK' ? (
                      <Button size="sm" onClick={() => setUnblockTarget(p)}>
                        Unblock
                      </Button>
                    ) : p.is_hidden_by_admin ? (
                      <Button size="sm" onClick={() => restoreProduct.mutate(p.id)}>
                        Restore
                      </Button>
                    ) : (
                      <>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setHideTarget({ type: 'product', id: p.id });
                            setReason('');
                          }}
                        >
                          Hide
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => void openBlockDialog(p)}
                        >
                          Take down
                        </Button>
                      </>
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
            onReset={() => {
              setReviewFilters({});
              clearPin();
            }}
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
        open={Boolean(blockTarget)}
        onOpenChange={(open) => {
          if (!open) setBlockTarget(null);
        }}
        title={`Take down ${blockTarget?.name ?? 'this product'}?`}
        description={blockImpact || 'Checking what this would cancel…'}
        confirmLabel="Take down"
        destructive
        loading={block.isPending}
        confirmDisabled={reason.trim().length < REASON_MIN_LENGTH}
        onConfirm={() => {
          if (!blockTarget) return;
          block.mutate(
            { id: blockTarget.id, reason },
            {
              onSuccess: () => {
                setBlockTarget(null);
                setReason('');
              },
            },
          );
        }}
      >
        <p className="admin-moderation-page__warning">
          Use this only when the item must not change hands at all. To look into something
          without cancelling anyone&rsquo;s order, hide it instead.
        </p>
        <Textarea
          className="admin-moderation-page__reason"
          placeholder="Why is this being taken down?"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </ConfirmDialog>
      <ConfirmDialog
        open={Boolean(unblockTarget)}
        onOpenChange={(open) => {
          if (!open) setUnblockTarget(null);
        }}
        title={`Put ${unblockTarget?.name ?? 'this product'} back on sale?`}
        description="The orders cancelled by the takedown are not reinstated. Those shoppers were told their order was off and may have bought elsewhere; they would have to order again."
        confirmLabel="Put back on sale"
        loading={unblock.isPending}
        onConfirm={() => {
          if (!unblockTarget) return;
          unblock.mutate(unblockTarget.id, { onSuccess: () => setUnblockTarget(null) });
        }}
      />
    </div>
  );
}
