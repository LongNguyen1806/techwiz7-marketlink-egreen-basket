import { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { EmptyState } from '../../components/feedback/EmptyState';
import { LazyImage } from '../../components/common/LazyImage';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { PriceTag } from '../../components/common/PriceTag';
import { QuantityStepper } from '../../components/common/QuantityStepper';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { ROUTES } from '../../constants/routes';
import { useDebouncedSearchParam } from '../../hooks/common/useDebouncedSearchParam';
import { useDebouncedValue } from '../../hooks/common/useDebouncedValue';
import { useUrlFilters } from '../../hooks/common/useUrlFilters';
import {
  useArchiveProduct,
  useFarmerProductList,
  useMarkProductSoldOut,
  useUpdateProductStock,
} from '../../hooks/queries/farmer/useFarmerProducts';
import { unitLabel } from '../../utils/labels';
import '../../styles/farmer/FarmerProductsPage.css';

const STATE_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'in_stock', label: 'In stock' },
  { value: 'out_of_stock', label: 'Out of stock' },
  { value: 'unavailable', label: 'Paused' },
  { value: 'hidden', label: 'Hidden by admin' },
  { value: 'archived', label: 'Archived' },
];

const AVAILABILITY = {
  IN_STOCK: { label: 'In stock', variant: 'success' },
  OUT_OF_STOCK: { label: 'Out of stock', variant: 'secondary' },
  UNAVAILABLE: { label: 'Paused', variant: 'secondary' },
};

// Clicks on the stepper are gathered and saved once the farmer pauses.
const STOCK_SAVE_DELAY_MS = 600;
const MAX_STOCK = 99999;

function statusOf(product) {
  if (product.is_archived) return { label: 'Archived', variant: 'secondary' };
  if (product.is_hidden_by_admin) return { label: 'Hidden by admin', variant: 'danger' };
  return AVAILABILITY[product.availability] ?? AVAILABILITY.UNAVAILABLE;
}

function StockCell({ product, locked }) {
  const updateStock = useUpdateProductStock();
  const [value, setValue] = useState(product.stock_quantity);
  const debounced = useDebouncedValue(value, STOCK_SAVE_DELAY_MS);
  const lastSaved = useRef(product.stock_quantity);

  // The server's number changed (an order, another tab, a rollback): show it.
  useEffect(() => {
    lastSaved.current = product.stock_quantity;
    setValue(product.stock_quantity);
  }, [product.stock_quantity]);

  useEffect(() => {
    if (debounced === lastSaved.current) return;
    lastSaved.current = debounced;
    updateStock.mutate({ id: product.id, stockQuantity: debounced });
    // Only a settled new value should trigger a save.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  return (
    <div>
      <QuantityStepper value={value} min={0} max={MAX_STOCK} onChange={setValue} disabled={locked} />
      {product.held_quantity > 0 || product.pending_quantity > 0 ? (
        <p className="page-primitive__muted-xs">
          {product.held_quantity} held · {product.pending_quantity} awaiting approval
        </p>
      ) : null}
    </div>
  );
}

StockCell.propTypes = {
  product: PropTypes.object.isRequired,
  locked: PropTypes.bool.isRequired,
};

function ProductRow({ product, onArchive }) {
  const markSoldOut = useMarkProductSoldOut();
  // The backend refuses edits to archived or admin-hidden products.
  const locked = product.is_archived || product.is_hidden_by_admin;
  const status = statusOf(product);

  return (
    <tr className="page-primitive__table-row">
      <td className="page-primitive__table-td">
        <div className="page-primitive__row-inner">
          {product.image ? (
            <LazyImage src={product.image} alt="" className="page-primitive__thumb-sm" />
          ) : (
            <div className="page-primitive__thumb-fallback" />
          )}
          <div>
            <Link
              to={ROUTES.FARMER.PRODUCT_EDIT(product.id)}
              className="page-primitive__font-medium page-primitive__link-underline"
            >
              {product.name}
            </Link>
            <p className="page-primitive__muted-xs">{product.category?.name}</p>
          </div>
        </div>
      </td>
      <td className="page-primitive__table-td">
        <PriceTag amount={product.price} unit={unitLabel(product.unit)} />
      </td>
      <td className="page-primitive__table-td">
        <StockCell product={product} locked={locked} />
      </td>
      <td className="page-primitive__table-td">
        <Badge variant={status.variant}>{status.label}</Badge>
      </td>
      <td className="page-primitive__table-td">
        <div className="page-primitive__actions-row">
          <Button asChild size="sm" variant="outline">
            <Link to={ROUTES.FARMER.PRODUCT_EDIT(product.id)}>Edit</Link>
          </Button>
          {!locked && product.stock_quantity > 0 ? (
            <Button
              size="sm"
              variant="outline"
              data-write
              loading={markSoldOut.isPending}
              onClick={() => markSoldOut.mutate(product.id)}
            >
              Mark sold out
            </Button>
          ) : null}
          {!product.is_archived ? (
            <Button size="sm" variant="destructive" data-write onClick={() => onArchive(product)}>
              Archive
            </Button>
          ) : null}
        </div>
      </td>
    </tr>
  );
}

ProductRow.propTypes = {
  product: PropTypes.object.isRequired,
  onArchive: PropTypes.func.isRequired,
};

export default function FarmerProductsPage() {
  const { filters, setFilters } = useUrlFilters({ state: '' });
  const search = useDebouncedSearchParam('q');
  const query = useFarmerProductList({ q: search.term || undefined, state: filters.state || undefined });
  const archive = useArchiveProduct();
  const [archiving, setArchiving] = useState(null);

  const products = query.data?.products ?? [];
  const hasFilters = Boolean(search.term || filters.state);

  let body;
  if (query.isPending) body = <PageSkeleton />;
  else if (query.isError && !query.data) {
    body = <EmptyState title="Products couldn't be loaded" actionLabel="Try again" onAction={() => query.refetch()} />;
  } else if (products.length === 0) {
    body = hasFilters ? (
      <EmptyState
        title="No products match"
        description="Try another search or status."
        actionLabel="Clear filters"
        onAction={() => {
          search.clear();
          setFilters({ state: '' });
        }}
      />
    ) : (
      <EmptyState title="No produce listed yet" description="Add your first item so shoppers can pre-order from your stall." />
    );
  } else {
    body = (
      <>
        <div className="page-primitive__table-wrap" aria-busy={query.isFetching}>
          <table className="page-primitive__table page-primitive__table-min-720">
            <thead className="page-primitive__table-head">
              <tr>
                <th className="page-primitive__table-th">Product</th>
                <th className="page-primitive__table-th">Price</th>
                <th className="page-primitive__table-th">Stock</th>
                <th className="page-primitive__table-th">Status</th>
                <th className="page-primitive__table-th">Actions</th>
              </tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <ProductRow key={product.id} product={product} onArchive={setArchiving} />
              ))}
            </tbody>
          </table>
        </div>
        {query.hasNextPage ? (
          <div className="page-primitive__justify-center-row">
            <Button variant="outline" size="sm" loading={query.isFetchingNextPage} onClick={() => query.fetchNextPage()}>
              Load more
            </Button>
          </div>
        ) : null}
      </>
    );
  }

  return (
    <div className="farmer-products-page">
      <PageHeader
        title="Your produce"
        description="Keep stock fresh, update prices, and mark sold-out items."
        actions={
          <Button asChild data-write>
            <Link to={ROUTES.FARMER.PRODUCT_NEW}>Add produce</Link>
          </Button>
        }
      />

      <form className="page-primitive__actions-row" role="search" onSubmit={(event) => event.preventDefault()}>
        <Input
          type="search"
          label="Search products"
          value={search.value}
          onChange={search.onChange}
          onKeyDown={search.onKeyDown}
          className="page-primitive__input-narrow"
        />
        <select
          className="page-primitive__select"
          aria-label="Filter by status"
          value={filters.state}
          onChange={(event) => setFilters({ state: event.target.value })}
        >
          {STATE_OPTIONS.map((option) => (
            <option key={option.value || 'all'} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </form>

      {body}

      <ConfirmDialog
        open={archiving !== null}
        onOpenChange={(open) => !open && setArchiving(null)}
        title={`Archive ${archiving?.name ?? 'this product'}?`}
        description="It stops being offered to shoppers. Open orders that include it are not affected."
        confirmLabel="Archive"
        destructive
        loading={archive.isPending}
        onConfirm={() => archive.mutate(archiving.id, { onSettled: () => setArchiving(null) })}
      />
    </div>
  );
}
