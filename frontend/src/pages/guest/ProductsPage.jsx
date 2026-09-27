import { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { X } from 'lucide-react';
import { Pagination } from '../../components/common/Pagination';
import { ProductCard } from '../../components/common/cards/ProductCard';
import { ProductCardSkeletonGrid } from '../../components/common/cards/ProductCardSkeleton';
import { EmptyState } from '../../components/feedback/EmptyState';
import { Input } from '../../components/ui/Input';
import { useAddToCart } from '../../hooks/common/useAddToCart';
import { useDebouncedSearchParam } from '../../hooks/common/useDebouncedSearchParam';
import { useUrlFilters } from '../../hooks/common/useUrlFilters';
import { useCategories, usePublicMarkets, usePublicProducts } from '../../hooks/queries/guest/usePublicCatalog';
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
  page: 1,
};

const MARKET_OPTIONS_PARAMS = { ordering: 'name', page_size: 20 };
const PAGE_SIZE = 20;

// The slider runs from $0 to the dearest listing, rounded up to a whole dollar. One request
// for the top price is enough to find that end; sold-out listings count, since the shopper
// can include them.
const TOP_PRICE_PARAMS = { ordering: 'price_desc', page_size: 5, in_stock: false };
const PRICE_STEP = 0.5;
const FALLBACK_CEILING = 20;

function parseIds(raw) {
  return raw
    .split(',')
    .map((part) => part.trim())
    .filter((part) => /^\d+$/.test(part));
}

function clampPrice(raw, fallback, ceiling) {
  const value = Number(raw);
  if (raw === '' || !Number.isFinite(value)) return fallback;
  return Math.min(Math.max(value, 0), ceiling);
}

function priceParam(value) {
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

/**
 * Two thumbs on one track. The labels follow the thumbs while dragging; the filter is applied
 * when the thumb is let go, so a drag does not fire a request per step. $0 at the bottom and
 * the top of the track mean "no limit" on that side and leave the URL parameter out.
 */
function PriceRange({ min, max, ceiling, onApply }) {
  const [range, setRange] = useState(() => {
    const low = clampPrice(min, 0, ceiling);
    return [low, Math.max(low, clampPrice(max, ceiling, ceiling))];
  });
  const [low, high] = range;

  const commit = () => {
    const next = {
      price_min: low > 0 ? priceParam(low) : '',
      price_max: high < ceiling ? priceParam(high) : '',
    };
    if (next.price_min !== min || next.price_max !== max) onApply(next);
  };
  const commitHandlers = { onPointerUp: commit, onKeyUp: commit, onBlur: commit };

  const percent = (value) => (value / ceiling) * 100;
  // When both thumbs meet at the top, the lower one must stay on top or it can never move again.
  const lowOnTop = low >= ceiling - PRICE_STEP;

  return (
    <div>
      <div className="products-page__price-head">
        <p className="products-page__filter-label">Price range ($)</p>
        <p className="products-page__price-value" aria-live="polite">
          {`${formatMoney(low)} – ${formatMoney(high)}`}
        </p>
      </div>
      <div
        className="products-page__range"
        style={{ '--range-from': `${percent(low)}%`, '--range-to': `${percent(high)}%` }}
      >
        <div className="products-page__range-track" aria-hidden>
          <div className="products-page__range-fill" />
        </div>
        <input
          type="range"
          className={`products-page__range-input${lowOnTop ? ' products-page__range-input--top' : ''}`}
          min={0}
          max={ceiling}
          step={PRICE_STEP}
          value={low}
          aria-label="Minimum price"
          aria-valuetext={formatMoney(low)}
          onChange={(event) => setRange([Math.min(Number(event.target.value), high), high])}
          {...commitHandlers}
        />
        <input
          type="range"
          className="products-page__range-input"
          min={0}
          max={ceiling}
          step={PRICE_STEP}
          value={high}
          aria-label="Maximum price"
          aria-valuetext={formatMoney(high)}
          onChange={(event) => setRange([low, Math.max(Number(event.target.value), low)])}
          {...commitHandlers}
        />
      </div>
      <div className="products-page__range-scale" aria-hidden>
        <span>{formatMoney(0)}</span>
        <span>{formatMoney(ceiling)}</span>
      </div>
    </div>
  );
}

PriceRange.propTypes = {
  min: PropTypes.string.isRequired,
  max: PropTypes.string.isRequired,
  ceiling: PropTypes.number.isRequired,
  onApply: PropTypes.func.isRequired,
};

export default function ProductsPage() {
  const { filters, setFilters, resetFilters } = useUrlFilters(FILTER_DEFAULTS);
  const search = useDebouncedSearchParam('q');
  const { addToCart, requireSignIn } = useAddToCart();
  const categoriesQuery = useCategories();
  const marketsQuery = usePublicMarkets(MARKET_OPTIONS_PARAMS);
  const topPriceQuery = usePublicProducts(TOP_PRICE_PARAMS);
  const topPrice = Number(topPriceQuery.data?.results?.[0]?.price);
  const priceCeiling = Number.isFinite(topPrice) && topPrice > 0 ? Math.ceil(topPrice) : FALLBACK_CEILING;
  const resultsRef = useRef(null);

  const categoryIds = parseIds(filters.category);
  
  const ordering = SORT_OPTIONS.some((option) => option.value === filters.ordering)
    ? filters.ordering
    : FILTER_DEFAULTS.ordering;
  const page = Math.max(1, Math.floor(filters.page));
  const productsQuery = usePublicProducts({
    q: search.term || undefined,
    category: categoryIds.length ? categoryIds.join(',') : undefined,
    market_id: filters.market_id || undefined,
    price_min: filters.price_min || undefined,
    price_max: filters.price_max || undefined,
    in_stock: filters.in_stock ? undefined : false,
    ordering,
    page,
    page_size: PAGE_SIZE,
  });
  const pageData = productsQuery.data;
  const products = pageData?.results ?? [];

  // A page past the end (an old link, or the list shrank) is a 404 from the API: go to page 1.
  const pageMissing = page > 1 && productsQuery.isError && productsQuery.error?.status === 404;
  useEffect(() => {
    if (pageMissing) setFilters({ page: 1 }, { replace: true });
  }, [pageMissing, setFilters]);

  const goToPage = (next) => {
    setFilters({ page: next });
    resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

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
  // While a new sort, filter or page loads, skeletons replace the old list rather than the old
  // cards staying up and then being reshuffled in place.
  if (productsQuery.isPending || productsQuery.isPlaceholderData) {
    results = <ProductCardSkeletonGrid count={6} className="products-page__grid" />;
  } else if (!pageData) {
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
        <p className="products-page__count">
          {`Showing ${(pageData.page - 1) * pageData.page_size + 1}–${(pageData.page - 1) * pageData.page_size + products.length} of ${pageData.count}`}
        </p>
        <div className="products-page__grid" aria-busy={productsQuery.isFetching}>
          {products.map((product) => (
            <ProductCard key={product.id} product={product} onAddToCart={addToCart} onRequireSignIn={requireSignIn} />
          ))}
        </div>
        <Pagination
          className="products-page__pagination"
          page={pageData.page}
          totalPages={pageData.total_pages}
          disabled={productsQuery.isPlaceholderData}
          onChange={goToPage}
        />
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
              key={`${filters.price_min}|${filters.price_max}|${priceCeiling}`}
              min={filters.price_min}
              max={filters.price_max}
              ceiling={priceCeiling}
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

          <div ref={resultsRef} className="products-page__results">
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
