import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';

import { adminApi } from '@/api/admin/adminApi';
import {
  useBlockModerationProduct,
  useHideModerationItem,
  useModerationProducts,
  useRestoreModerationProduct,
  useUnblockModerationProduct,
} from '../../hooks/queries/admin/useAdminModeration';
import { PriceGuidelinesPanel } from './AdminPriceGuidelinesPage';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { Scale } from 'lucide-react';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { EmptyState } from '@/components/feedback/EmptyState';
import { PageHeader } from '@/components/common/PageHeader';
import { PageSkeleton } from '@/components/feedback/PageSkeleton';
import { LazyImage } from '@/components/common/LazyImage';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Textarea } from '@/components/ui/Textarea';
import { SortSelect } from '@/components/common/SortSelect';
import { FilterBar } from '@/components/common/table/FilterBar';
import { REVIEW_STATE, reviewStateBadge } from '@/utils/reviewState';

import './AdminProductsPage.css';

const REASON_MIN_LENGTH = 5;

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
    name: 'review_status',
    label: 'Review',
    type: 'select',
    allLabel: 'Any state',
    options: REVIEW_STATE.map(({ value, label }) => ({ value, label })),
  },
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

const PRODUCT_SORT = [
  { value: 'name', label: 'Name A–Z' },
  { value: 'stall_name', label: 'Stall A–Z' },
  { value: '-price', label: 'Highest price' },
  { value: '-rating', label: 'Highest rated' },
  { value: 'rating', label: 'Lowest rated' },
  { value: 'oldest', label: 'Oldest first' },
];

export default function AdminProductsPage() {
  const [params, setParams] = useSearchParams();
  const [guidelinesOpen, setGuidelinesOpen] = useState(() => params.get('guidelines') === 'open');
  const [pinnedId] = useState(() => params.get('product_id') ?? undefined);

  const [filters, setFilters] = useState(() =>
    pinnedId ? { product_id: pinnedId } : {},
  );
  const [ordering, setOrdering] = useState(undefined);
  const [hideTarget, setHideTarget] = useState(null);
  const [blockTarget, setBlockTarget] = useState(null);
  const [blockImpact, setBlockImpact] = useState('');
  const [unblockTarget, setUnblockTarget] = useState(null);
  const [reason, setReason] = useState('');

  const query = useModerationProducts({ ...filters, ordering });
  const hide = useHideModerationItem();
  const block = useBlockModerationProduct();
  const unblock = useUnblockModerationProduct();
  const restore = useRestoreModerationProduct();

  const clearPin = () => {
    if (!params.size) return;
    setParams(new URLSearchParams(), { replace: true });
  };

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
        title="Products"
        description="Everything on the shelves. Hide one while you look into it, or take it down if it must not be sold at all."
        actions={
          <Button variant="outline" onClick={() => setGuidelinesOpen(true)}>
            <Scale aria-hidden="true" className="admin-products-page__btn-icon" />
            Price guidelines
          </Button>
        }
      />

      {pinnedId ? (
        <p className="admin-products-page__pin">
          Showing one item.
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
        fields={PRODUCT_FILTERS}
        value={filters}
        onChange={setFilters}
        onReset={() => {
          setFilters({});
          clearPin();
        }}
      />
      <SortSelect
        id="product-sort"
        options={PRODUCT_SORT}
        value={ordering}
        onChange={setOrdering}
      />

      <div className="admin-products-page__list">
        {query.isLoading ? (
          <PageSkeleton />
        ) : !query.data?.results.length ? (
          <EmptyState title="No products match this search" />
        ) : (
          query.data.results.map((p) => {
            const badge = reviewStateBadge(p.review_status);
            return (
              <div key={p.id} className="admin-products-page__row">
                <div className="admin-products-page__info">
                  <LazyImage src={p.image} alt="" className="admin-products-page__thumb" />
                  <div>
                    <p className="admin-products-page__name">{p.name}</p>
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
                    <div className="admin-products-page__badges">
                      {badge ? <Badge variant={badge.variant}>{badge.label}</Badge> : null}
                      {p.is_hidden_by_admin ? (
                        <Badge variant="danger">
                          {moderationCopy(p).label}: {p.hidden_reason}
                        </Badge>
                      ) : null}
                    </div>
                    {p.review_status === 'REJECTED' && p.review_note ? (
                      <p className="admin-products-page__note">{p.review_note}</p>
                    ) : null}
                  </div>
                </div>
                <div className="page-primitive__actions-row">
                  {p.moderation_action === 'BLOCK' ? (
                    <Button size="sm" onClick={() => setUnblockTarget(p)}>
                      Unblock
                    </Button>
                  ) : p.is_hidden_by_admin ? (
                    <Button size="sm" onClick={() => restore.mutate(p.id)}>
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
            );
          })
        )}
      </div>

      <ConfirmDialog
        open={Boolean(hideTarget)}
        onOpenChange={(open) => {
          if (!open) setHideTarget(null);
        }}
        title="Hide this product"
        description="Add a short reason before hiding it from shoppers. Orders already placed for it stand."
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
          className="admin-products-page__reason"
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
        <p className="admin-products-page__warning">
          Use this only when the item must not change hands at all. To look into something
          without cancelling anyone&rsquo;s order, hide it instead.
        </p>
        <Textarea
          className="admin-products-page__reason"
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

      <Dialog
        open={guidelinesOpen}
        onOpenChange={(open) => {
          setGuidelinesOpen(open);
          if (!open && params.get('guidelines')) {
            const next = new URLSearchParams(params);
            next.delete('guidelines');
            setParams(next, { replace: true });
          }
        }}
      >
        <DialogContent className="admin-products-page__guidelines">
          <DialogHeader>
            <DialogTitle>Price guidelines</DialogTitle>
          </DialogHeader>
          <PriceGuidelinesPanel />
        </DialogContent>
      </Dialog>
    </div>
  );
}
