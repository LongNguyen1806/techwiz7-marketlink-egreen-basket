import { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { MoreHorizontal } from 'lucide-react';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { EmptyState } from '../../components/feedback/EmptyState';
import { LazyImage } from '../../components/common/LazyImage';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { PageStatus, Pagination } from '../../components/common/Pagination';
import { PriceTag } from '../../components/common/PriceTag';
import { QuantityStepper } from '../../components/common/QuantityStepper';
import { MarketChecklist, isSellingMarket } from '../../components/farmer/MarketChecklist';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../../components/ui/DropdownMenu';
import { Input } from '../../components/ui/Input';
import { ROUTES } from '../../constants/routes';
import { useDebouncedSearchParam } from '../../hooks/common/useDebouncedSearchParam';
import { useDebouncedValue } from '../../hooks/common/useDebouncedValue';
import { useUrlFilters } from '../../hooks/common/useUrlFilters';
import { readPage, usePageParam } from '../../hooks/common/usePageParam';
import {
  useArchiveProduct,
  useBulkProducts,
  useFarmerProductCounts,
  useFarmerProductList,
  useMarkProductSoldOut,
  useUpdateProductStock,
} from '../../hooks/queries/farmer/useFarmerProducts';
import { useFarmerMarkets } from '../../hooks/queries/farmer/useFarmerMarkets';
import { useFarmerProfile } from '../../hooks/queries/farmer/useFarmerProfile';
import { useCategories } from '../../hooks/queries/guest/usePublicCatalog';
import { orderWindowLabel as orderLimits, unitLabel } from '../../utils/labels';
import '../../styles/farmer/FarmerProductsPage.css';

const STATUS_CHIPS = [
  { value: '', label: 'All', countKey: 'all' },
  { value: 'in_stock', label: 'On sale', countKey: 'in_stock' },
  { value: 'in_review', label: 'In review', countKey: 'in_review' },
  { value: 'out_of_stock', label: 'Out of stock', countKey: 'out_of_stock' },
  { value: 'unavailable', label: 'Paused', countKey: 'unavailable' },
  { value: 'rejected', label: 'Rejected', countKey: 'rejected' },
  { value: 'hidden', label: 'Hidden by admin', countKey: 'hidden', optional: true },
  { value: 'archived', label: 'Archived', countKey: 'archived', optional: true },
];

const REVIEW = {
  PENDING: { label: 'In review', variant: 'warning' },
  REJECTED: { label: 'Rejected', variant: 'danger' },
};

const AVAILABILITY = {
  IN_STOCK: { label: 'On sale', variant: 'success' },
  OUT_OF_STOCK: { label: 'Out of stock', variant: 'secondary' },
  UNAVAILABLE: { label: 'Paused', variant: 'secondary' },
};

const STOCK_SAVE_DELAY_MS = 600;
const MAX_STOCK = 99999;

function orderWindowLabel(product) {
  return orderLimits({ min: product.min_per_order, max: product.max_per_order, unit: product.unit });
}

function statusOf(product) {
  if (product.is_archived) return { label: 'Archived', variant: 'secondary' };
  if (product.is_hidden_by_admin) return { label: 'Hidden by admin', variant: 'danger' };
  if (REVIEW[product.review_status]) return REVIEW[product.review_status];
  return AVAILABILITY[product.availability] ?? AVAILABILITY.UNAVAILABLE;
}

function StockCell({ product, locked }) {
  const updateStock = useUpdateProductStock();
  const [value, setValue] = useState(product.stock_quantity);
  const debounced = useDebouncedValue(value, STOCK_SAVE_DELAY_MS);
  const lastSaved = useRef(product.stock_quantity);

  useEffect(() => {
    lastSaved.current = product.stock_quantity;
    setValue(product.stock_quantity);
  }, [product.stock_quantity]);

  useEffect(() => {
    if (debounced === lastSaved.current) return;
    lastSaved.current = debounced;
    updateStock.mutate({ id: product.id, stockQuantity: debounced });
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

function MarketsCell({ product }) {
  if (product.is_archived) return <span className="page-primitive__muted-xs">—</span>;
  if (!product.markets?.length) {
    return <p className="page-primitive__danger-sm">Not sold at any market. Edit it to choose where.</p>;
  }
  return (
    <ul className="farmer-products-page__market-tags">
      {product.markets.map((market) => (
        <li key={market.market_id} className="farmer-products-page__market-tag">
          {market.market_name}
        </li>
      ))}
    </ul>
  );
}

MarketsCell.propTypes = {
  product: PropTypes.object.isRequired,
};

function ProductRow({ product, selected, onSelect, onArchive, onBulk }) {
  const markSoldOut = useMarkProductSoldOut();
  const locked = product.is_archived || product.is_hidden_by_admin;
  const status = statusOf(product);

  return (
    <tr className={`page-primitive__table-row${selected ? ' farmer-products-page__row--selected' : ''}`}>
      <td className="page-primitive__table-td farmer-products-page__select-cell">
        <input
          type="checkbox"
          className="farmer-products-page__checkbox"
          aria-label={`Select ${product.name}`}
          checked={selected}
          disabled={product.is_archived}
          onChange={() => onSelect(product.id)}
        />
      </td>
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
            {product.review_status === 'PENDING' ? (
              <p className="page-primitive__muted-xs">Shoppers will see it once it passes review.</p>
            ) : null}
            {product.review_status === 'REJECTED' ? (
              <p className="page-primitive__danger-sm">
                Not approved{product.review_note ? `: ${product.review_note}` : ''}. Edit it to send it for review again.
              </p>
            ) : null}
          </div>
        </div>
      </td>
      <td className="page-primitive__table-td">
        <PriceTag amount={product.price} unit={unitLabel(product.unit)} />
        {product.min_per_order > 1 || product.max_per_order ? (
          <p className="page-primitive__muted-xs">{orderWindowLabel(product)}</p>
        ) : null}
      </td>
      <td className="page-primitive__table-td">
        <StockCell product={product} locked={locked} />
      </td>
      <td className="page-primitive__table-td">
        <MarketsCell product={product} />
      </td>
      <td className="page-primitive__table-td">
        <Badge variant={status.variant} className="farmer-products-page__status">
          {status.label}
        </Badge>
      </td>
      <td className="page-primitive__table-td">
        <div className="page-primitive__actions-row">
          <Button asChild size="sm" variant="outline">
            <Link to={ROUTES.FARMER.PRODUCT_EDIT(product.id)}>Edit</Link>
          </Button>
          {!product.is_archived ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="icon" variant="ghost" aria-label={`More actions for ${product.name}`} data-write>
                  <MoreHorizontal aria-hidden className="farmer-products-page__more-icon" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {!locked && product.stock_quantity > 0 ? (
                  <DropdownMenuItem onSelect={() => markSoldOut.mutate(product.id)}>Mark sold out</DropdownMenuItem>
                ) : null}
                {!locked ? (
                  <DropdownMenuItem
                    onSelect={() => onBulk({ productIds: [product.id], action: product.is_available ? 'pause' : 'resume' })}
                  >
                    {product.is_available ? 'Pause sales' : 'Open for sale'}
                  </DropdownMenuItem>
                ) : null}
                <DropdownMenuSeparator />
                <DropdownMenuItem className="farmer-products-page__danger-item" onSelect={() => onArchive(product)}>
                  Archive…
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : null}
        </div>
      </td>
    </tr>
  );
}

ProductRow.propTypes = {
  product: PropTypes.object.isRequired,
  selected: PropTypes.bool.isRequired,
  onSelect: PropTypes.func.isRequired,
  onArchive: PropTypes.func.isRequired,
  onBulk: PropTypes.func.isRequired,
};

export default function FarmerProductsPage() {
  const { filters, setFilters } = useUrlFilters({ state: '', category: 0, market: 0, page: 1 });
  const search = useDebouncedSearchParam('q');
  const categoriesQuery = useCategories();
  const marketsQuery = useFarmerMarkets();
  const profileQuery = useFarmerProfile();
  const canListProducts = profileQuery.data?.can_list_products !== false;

  const scope = {
    q: search.term || undefined,
    category_id: filters.category || undefined,
    market_id: filters.market || undefined,
  };
  const query = useFarmerProductList({ ...scope, state: filters.state || undefined, page: readPage(filters) });
  const countsQuery = useFarmerProductCounts(scope);
  const goToPage = usePageParam({ filters, setFilters, query });
  const archive = useArchiveProduct();
  const bulk = useBulkProducts();
  const [archiving, setArchiving] = useState(null);
  const [selected, setSelected] = useState(() => new Set());
  const [settingMarkets, setSettingMarkets] = useState(false);
  const [bulkMarketIds, setBulkMarketIds] = useState([]);

  const farmerMarkets = marketsQuery.data ?? [];
  const sellingMarketIds = farmerMarkets.filter(isSellingMarket).map((item) => item.market.id);
  const counts = countsQuery.data ?? {};
  const products = query.data?.products ?? [];
  const hasFilters = Boolean(search.term || filters.state || filters.category || filters.market);
  const filterKey = `${search.term}|${filters.state}|${filters.category}|${filters.market}|${readPage(filters)}`;

  useEffect(() => {
    setSelected(new Set());
  }, [filterKey]);

  const toggleSelected = (id) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const selectable = products.filter((product) => !product.is_archived).map((product) => product.id);
  const allSelected = selectable.length > 0 && selectable.every((id) => selected.has(id));
  const toggleAll = () => setSelected(allSelected ? new Set() : new Set(selectable));

  const runBulk = (payload, options) => bulk.mutate(payload, options);
  const selectedIds = [...selected];
  const clearSelection = () => setSelected(new Set());

  const openSetMarkets = () => {
    setBulkMarketIds(sellingMarketIds);
    setSettingMarkets(true);
  };

  let body;
  if (query.isPending) body = <PageSkeleton />;
  else if (query.isError && !query.data) {
    body = <EmptyState title="Products couldn't be loaded" actionLabel="Try again" onAction={() => query.refetch()} />;
  } else if (products.length === 0) {
    const onlyMarketChosen = Boolean(filters.market) && !search.term && !filters.state && !filters.category;
    const marketName = farmerMarkets.find((item) => item.market.id === filters.market)?.market.name;
    body = onlyMarketChosen ? (
      <EmptyState
        title={`Nothing is sold at ${marketName ?? 'this market'} yet`}
        description="Go to All markets, tick the produce you bring here, then use Choose markets… — or tick this market when you edit an item."
        actionLabel="Show all markets"
        onAction={() => setFilters({ market: 0 })}
      />
    ) : hasFilters ? (
      <EmptyState
        title="No products match"
        description="Try another market, search, category or status."
        actionLabel="Clear filters"
        onAction={() => {
          search.clear();
          setFilters({ state: '', category: 0, market: 0 });
        }}
      />
    ) : (
      <EmptyState title="No produce listed yet" description="Add your first item so shoppers can pre-order from your stall." />
    );
  } else {
    body = (
      <>
        <PageStatus page={query.data.page} pageSize={query.data.pageSize} total={query.data.total} shown={products.length} />
        {selected.size > 0 ? (
          <div className="farmer-products-page__bulk-bar" role="region" aria-label="Bulk actions">
            <span className="farmer-products-page__bulk-count">{selected.size} selected</span>
            <Button size="sm" variant="outline" data-write loading={bulk.isPending}
              onClick={() => runBulk({ productIds: selectedIds, action: 'sold_out' }, { onSuccess: clearSelection })}>
              Mark sold out
            </Button>
            <Button size="sm" variant="outline" data-write loading={bulk.isPending}
              onClick={() => runBulk({ productIds: selectedIds, action: 'pause' }, { onSuccess: clearSelection })}>
              Pause sales
            </Button>
            <Button size="sm" variant="outline" data-write loading={bulk.isPending}
              onClick={() => runBulk({ productIds: selectedIds, action: 'resume' }, { onSuccess: clearSelection })}>
              Open for sale
            </Button>
            <Button size="sm" variant="outline" data-write disabled={!sellingMarketIds.length} onClick={openSetMarkets}>
              Choose markets…
            </Button>
            <Button size="sm" variant="ghost" onClick={clearSelection}>
              Clear
            </Button>
          </div>
        ) : null}
        <div className="page-primitive__table-wrap" aria-busy={query.isFetching}>
          <table className="page-primitive__table page-primitive__table-min-720">
            <thead className="page-primitive__table-head">
              <tr>
                <th className="page-primitive__table-th farmer-products-page__select-cell">
                  <input
                    type="checkbox"
                    className="farmer-products-page__checkbox"
                    aria-label="Select all on this page"
                    checked={allSelected}
                    disabled={!selectable.length}
                    onChange={toggleAll}
                  />
                </th>
                <th className="page-primitive__table-th">Product</th>
                <th className="page-primitive__table-th">Price</th>
                <th className="page-primitive__table-th">Stock</th>
                <th className="page-primitive__table-th">Sold at</th>
                <th className="page-primitive__table-th">Status</th>
                <th className="page-primitive__table-th">Actions</th>
              </tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <ProductRow
                  key={product.id}
                  product={product}
                  selected={selected.has(product.id)}
                  onSelect={toggleSelected}
                  onArchive={setArchiving}
                  onBulk={runBulk}
                />
              ))}
            </tbody>
          </table>
        </div>
        <Pagination page={query.data.page} totalPages={query.data.totalPages} disabled={query.isPlaceholderData} onChange={goToPage} />
      </>
    );
  }

  return (
    <div className="farmer-products-page">
      <PageHeader
        title="Your produce"
        description="Choose where each item is sold, keep stock fresh, and pause or sell out in a click."
        actions={
          canListProducts ? (
            <Button asChild data-write>
              <Link to={ROUTES.FARMER.PRODUCT_NEW}>Add produce</Link>
            </Button>
          ) : (
            <Button disabled data-write>
              Add produce
            </Button>
          )
        }
      />
      {!canListProducts ? (
        <p className="page-primitive__warn-banner">
          You can list produce once an administrator approves your stall at a market. Check your requests in{' '}
          <Link to={ROUTES.FARMER.MARKETS}>Markets &amp; slots</Link>.
        </p>
      ) : null}

      {farmerMarkets.length > 1 ? (
        <div className="farmer-products-page__chips" role="group" aria-label="Filter by market">
          <button
            type="button"
            className={`farmer-products-page__chip${!filters.market ? ' is-active' : ''}`}
            onClick={() => setFilters({ market: 0 })}
          >
            All markets
          </button>
          {farmerMarkets.map((item) => {
            const selling = isSellingMarket(item);
            return (
              <button
                key={item.id}
                type="button"
                disabled={!selling}
                title={selling ? undefined : item.status !== 'APPROVED' ? 'Waiting for approval' : 'Closed by admin'}
                className={`farmer-products-page__chip${filters.market === item.market.id ? ' is-active' : ''}`}
                onClick={() => setFilters({ market: item.market.id })}
              >
                {item.market.name}
                {!selling ? <span className="farmer-products-page__chip-note"> · {item.status !== 'APPROVED' ? 'waiting' : 'closed'}</span> : null}
              </button>
            );
          })}
        </div>
      ) : null}

      <div className="farmer-products-page__chips" role="group" aria-label="Filter by status">
        {STATUS_CHIPS.filter((chip) => !chip.optional || counts[chip.countKey] > 0 || filters.state === chip.value).map(
          (chip) => (
            <button
              key={chip.value || 'all'}
              type="button"
              className={`farmer-products-page__chip${filters.state === chip.value ? ' is-active' : ''}`}
              onClick={() => setFilters({ state: chip.value })}
            >
              {chip.label}
              <span className="farmer-products-page__chip-count">{counts[chip.countKey] ?? '·'}</span>
            </button>
          ),
        )}
      </div>

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
          aria-label="Filter by category"
          value={filters.category}
          onChange={(event) => setFilters({ category: Number(event.target.value) })}
        >
          <option value={0}>All categories</option>
          {(categoriesQuery.data ?? []).map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
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

      <ConfirmDialog
        open={settingMarkets}
        onOpenChange={setSettingMarkets}
        title={`Where should ${selected.size} product${selected.size === 1 ? '' : 's'} be sold?`}
        description="Shoppers can only collect these items at the markets you tick. Stock stays shared."
        confirmLabel="Save markets"
        loading={bulk.isPending}
        confirmDisabled={!bulkMarketIds.length}
        onConfirm={() =>
          runBulk(
            { productIds: selectedIds, action: 'set_markets', marketIds: bulkMarketIds },
            {
              onSuccess: () => {
                setSettingMarkets(false);
                clearSelection();
              },
            },
          )
        }
      >
        <MarketChecklist markets={farmerMarkets} value={bulkMarketIds} onChange={setBulkMarketIds} />
      </ConfirmDialog>
    </div>
  );
}
