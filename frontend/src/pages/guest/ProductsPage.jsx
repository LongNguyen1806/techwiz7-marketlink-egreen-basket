import { useState } from 'react';
import PropTypes from 'prop-types';
import { X } from 'lucide-react';
import { ProductCard } from '../../components/common/cards/ProductCard';
import { EmptyState } from '../../components/feedback/EmptyState';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Skeleton } from '../../components/ui/Skeleton';
import { useAddToCart } from '../../hooks/common/useAddToCart';
import { useDebouncedSearchParam } from '../../hooks/common/useDebouncedSearchParam';
import { useUrlFilters } from '../../hooks/common/useUrlFilters';
import { useCategories, usePublicMarkets, usePublicProductList } from '../../hooks/queries/guest/usePublicCatalog';
import { formatMoney } from '../../utils/formatters';
import '../../styles/guest/ProductsPage.css';

const SORT_OPTIONS = [
  { value: 'newest', label: 'Newest arrivals' },
  { value: 'price_asc', label: 'Price: low to high' },
  { value: 'price_desc', label: 'Price: high to low' },
  { value: 'rating', label: 'Top rated' },
];



const FILTER_DEFAULTS = {
  category: '',
  market_id: '',
  price_min: '',
  price_max: '',
  in_stock: true,
  ordering: 'newest',
};

const MARKET_OPTIONS_PARAMS = { ordering: 'name', page_size: 20 };
const PRICE_PATTERN = /^\d+(\.\d{1,2})?$/;

function parseIds(raw) {
  return raw
    .split(',')
    .map((part) => part.trim())
    .filter((part) => /^\d+$/.test(part));
}

function priceError(min, max) {
  if (min && !PRICE_PATTERN.test(min)) return 'Use a price such as 2.50';
  if (max && !PRICE_PATTERN.test(max)) return 'Use a price such as 2.50';
  if (min && max && Number(min) > Number(max)) return 'The minimum must not be above the maximum';
  return null;
}


function PriceRange({ min, max, onApply }) {
  const [draft, setDraft] = useState({ min, max });
  const error = priceError(draft.min.trim(), draft.max.trim());

  const apply = () => {
    if (error) return;
    const next = { price_min: draft.min.trim(), price_max: draft.max.trim() };
    if (next.price_min !== min || next.price_max !== max) onApply(next);
  };
  const onKeyDown = (event) => {
    if (event.key === 'Enter') apply();
  };

  return (
    <div>
      <p className="products-page__filter-label">Price range ($)</p>
      <div className="products-page__price-row">
        <Input
          type="number"
          inputMode="decimal"
          min="0"
          step="0.01"
          label="Min"
          value={draft.min}
          onChange={(event) => setDraft((current) => ({ ...current, min: event.target.value }))}
          onBlur={apply}
          onKeyDown={onKeyDown}
        />
        <Input
          type="number"
          inputMode="decimal"
          min="0"
          step="0.01"
          label="Max"
          value={draft.max}
          onChange={(event) => setDraft((current) => ({ ...current, max: event.target.value }))}
          onBlur={apply}
          onKeyDown={onKeyDown}
        />
      </div>
      {error ? <p className="page-primitive__error">{error}</p> : null}
    </div>
  );
}

PriceRange.propTypes = {
  min: PropTypes.string.isRequired,
  max: PropTypes.string.isRequired,
  onApply: PropTypes.func.isRequired,
};

export default function ProductsPage() {
  const { filters, setFilters, resetFilters } = useUrlFilters(FILTER_DEFAULTS);
  const search = useDebouncedSearchParam('q');
  const { addToCart, requireSignIn } = useAddToCart();
  const categoriesQuery = useCategories();
  const marketsQuery = usePublicMarkets(MARKET_OPTIONS_PARAMS);

  const categoryIds = parseIds(filters.category);
  
  const ordering = SORT_OPTIONS.some((option) => option.value === filters.ordering)
    ? filters.ordering
    : FILTER_DEFAULTS.ordering;
  const productsQuery = usePublicProductList({
    q: search.term || undefined,
    category: categoryIds.length ? categoryIds.join(',') : undefined,
    market_id: filters.market_id || undefined,
    price_min: filters.price_min || undefined,
    price_max: filters.price_max || undefined,
    in_stock: filters.in_stock ? undefined : false,
    ordering,
  });
  const products = productsQuery.data?.products ?? [];

  const toggleCategory = (id) => {
    const key = String(id);
    const next = categoryIds.includes(key) ? categoryIds.filter((item) => item !== key) : [...categoryIds, key];
    setFilters({ category: next.join(',') });
  };

  const clearAll = () => {
    search.clear();
    resetFilters();
  };

  const chips = [];
  if (search.term) chips.push({ key: 'q', label: `“${search.term}”`, clear: search.clear });
  if (filters.market_id) {
    const name = marketsQuery.data?.results.find((market) => String(market.id) === filters.market_id)?.name;
    chips.push({ key: 'market', label: name ?? 'Selected market', clear: () => setFilters({ market_id: '' }) });
  }
  categoryIds.forEach((id) => {
    const name = categoriesQuery.data?.find((category) => String(category.id) === id)?.name;
    chips.push({ key: `category-${id}`, label: name ?? 'Category', clear: () => toggleCategory(id) });
  });
  if (filters.price_min || filters.price_max) {
    const from = filters.price_min ? formatMoney(filters.price_min) : 'Any';
    const to = filters.price_max ? formatMoney(filters.price_max) : 'any';
    chips.push({ key: 'price', label: `${from} – ${to}`, clear: () => setFilters({ price_min: '', price_max: '' }) });
  }
  if (!filters.in_stock) {
    chips.push({ key: 'stock', label: 'Including sold out', clear: () => setFilters({ in_stock: true }) });
  }

  let results;
  if (productsQuery.isPending) {
    results = (
      <div className="products-page__grid" aria-busy>
        {Array.from({ length: 6 }).map((_, index) => (
          <Skeleton key={index} className="products-page__skeleton" />
        ))}
      </div>
    );
  } else if (!productsQuery.data) {
    results = (
      <EmptyState title="Products couldn't be loaded" actionLabel="Try again" onAction={() => productsQuery.refetch()} />
    );
  } else if (products.length === 0) {
    results = (
      <EmptyState
        title="No produce matches your filters"
        description="Widen the price range, clear a category, or try a different search."
        actionLabel={chips.length > 0 ? 'Clear all filters' : undefined}
        onAction={chips.length > 0 ? clearAll : undefined}
      />
    );
  } else {
    results = (
      <>
        <div className="products-page__grid" aria-busy={productsQuery.isFetching}>
          {products.map((product) => (
            <ProductCard key={product.id} product={product} onAddToCart={addToCart} onRequireSignIn={requireSignIn} />
          ))}
        </div>
        <div className="products-page__load-more">
          {productsQuery.hasNextPage ? (
            <Button
              variant="outline"
              size="lg"
              className="products-page__btn-press"
              loading={productsQuery.isFetchingNextPage}
              onClick={() => productsQuery.fetchNextPage()}
            >
              Show more produce
            </Button>
          ) : (
            <p className="products-page__end-note">You have reached the end</p>
          )}
        </div>
      </>
    );
  }

  return (
    <div className="products-page">
      <section className="products-page__hero">
        <div className="products-page__hero-inner">
          <div className="products-page__hero-copy">
            <p className="products-page__eyebrow">Fresh from the stall</p>
            <h1 className="products-page__title">Market produce</h1>
            <p className="products-page__subtitle">
              Filter by category, price, market, or stock — then pre-order and pick up when it suits you.
            </p>
          </div>
        </div>
      </section>

      <div className="products-page__body">
        <div className="products-page__layout">
          <aside className="products-page__sidebar" aria-label="Filters">
            <div>
              <p className="products-page__filter-label">Search</p>
              <div className="products-page__search-wrap">
                <Input
                  type="search"
                  label="Search produce or stalls"
                  value={search.value}
                  onChange={search.onChange}
                  onKeyDown={search.onKeyDown}
                  className="products-page__search-input"
                />
              </div>
            </div>

            <div>
              <p className="products-page__filter-label">Categories</p>
              <div className="products-page__category-list">
                {(categoriesQuery.data ?? []).map((category) => {
                  const checked = categoryIds.includes(String(category.id));
                  return (
                    <label
                      key={category.id}
                      className={
                        checked ? 'products-page__check-row products-page__check-row--active' : 'products-page__check-row'
                      }
                    >
                      <input
                        type="checkbox"
                        className="products-page__checkbox"
                        checked={checked}
                        onChange={() => toggleCategory(category.id)}
                      />
                      {category.name}
                    </label>
                  );
                })}
              </div>
            </div>

            
            <PriceRange
              key={`${filters.price_min}|${filters.price_max}`}
              min={filters.price_min}
              max={filters.price_max}
              onApply={setFilters}
            />

            <div>
              <p className="products-page__filter-label">Market</p>
              <select
                className="products-page__select"
                aria-label="Market"
                value={filters.market_id}
                onChange={(event) => setFilters({ market_id: event.target.value })}
              >
                <option value="">All markets</option>
                {(marketsQuery.data?.results ?? []).map((market) => (
                  <option key={market.id} value={String(market.id)}>
                    {market.name}
                  </option>
                ))}
              </select>
            </div>

            <label
              className={
                filters.in_stock ? 'products-page__check-row products-page__check-row--active' : 'products-page__check-row'
              }
            >
              <input
                type="checkbox"
                className="products-page__checkbox"
                checked={filters.in_stock}
                onChange={(event) => setFilters({ in_stock: event.target.checked })}
              />
              In stock only
            </label>

            <div>
              <p className="products-page__filter-label">Sort by</p>
              <select
                className="products-page__select"
                aria-label="Sort by"
                value={ordering}
                onChange={(event) => setFilters({ ordering: event.target.value })}
              >
                {SORT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </aside>

          <div>
            {chips.length > 0 ? (
              <div className="products-page__chips">
                {chips.map((chip) => (
                  <button key={chip.key} type="button" className="products-page__chip" onClick={chip.clear}>
                    {chip.label}
                    <X className="products-page__chip-icon" aria-label="Remove filter" />
                  </button>
                ))}
              </div>
            ) : null}
            {results}
          </div>
        </div>
      </div>
    </div>
  );
}
