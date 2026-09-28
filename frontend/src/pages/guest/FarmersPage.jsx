import { FarmerCard } from '../../components/common/cards/FarmerCard';
import { EmptyState } from '../../components/feedback/EmptyState';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Skeleton } from '../../components/ui/Skeleton';
import { useAddToCart } from '../../hooks/common/useAddToCart';
import { useDebouncedSearchParam } from '../../hooks/common/useDebouncedSearchParam';
import { useUrlFilters } from '../../hooks/common/useUrlFilters';
import { usePublicFarmerList } from '../../hooks/queries/guest/usePublicCatalog';
import { useGeolocation } from '../../hooks/useGeolocation';
import '../../styles/guest/FarmersPage.css';

const SORT_OPTIONS = [
  { value: 'rating', label: 'Top rated' },
  { value: 'in_stock', label: 'Best stocked' },
  { value: 'distance', label: 'Nearest first' },
  { value: 'name', label: 'Name A–Z' },
];

export default function FarmersPage() {
  const { filters, setFilters } = useUrlFilters({ ordering: 'rating' });
  const search = useDebouncedSearchParam('q');
  const { lat, lng, requestLocation } = useGeolocation();
  const { requireSignIn } = useAddToCart();

  const hasLocation = lat !== null && lng !== null;
  const ordering = SORT_OPTIONS.some((option) => option.value === filters.ordering) ? filters.ordering : 'rating';

  const query = usePublicFarmerList({
    q: search.term || undefined,
    ordering,
    lat: hasLocation ? lat : undefined,
    lng: hasLocation ? lng : undefined,
  });
  const farmers = query.data?.farmers ?? [];
  const total = query.data?.total ?? 0;

  const changeSort = (value) => {
    if (value === 'distance' && !hasLocation) requestLocation();
    setFilters({ ordering: value });
  };

  let body;
  if (query.isPending) {
    body = (
      <div className="farmers-page__grid" aria-busy>
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="farmers-page__skeleton" />
        ))}
      </div>
    );
  } else if (!query.data) {
    body = <EmptyState title="Stalls couldn't be loaded" actionLabel="Try again" onAction={() => query.refetch()} />;
  } else if (farmers.length === 0) {
    body = (
      <EmptyState
        title="No stalls match your search"
        description="Try another name, or clear the search to see everyone."
        actionLabel={search.term ? 'Clear search' : undefined}
        onAction={search.term ? search.clear : undefined}
      />
    );
  } else {
    body = (
      <>
        <div className="farmers-page__grid" aria-busy={query.isFetching}>
          {farmers.map((farmer) => (
            <FarmerCard key={farmer.id} farmer={farmer} onRequireSignIn={requireSignIn} />
          ))}
        </div>
        {query.hasNextPage ? (
          <div className="page-primitive__justify-center-row">
            <Button variant="outline" loading={query.isFetchingNextPage} onClick={() => query.fetchNextPage()}>
              Show more stalls
            </Button>
          </div>
        ) : null}
      </>
    );
  }

  return (
    <div className="farmers-page">
      <section className="farmers-page__hero">
        <div className="farmers-page__hero-inner">
          <div className="farmers-page__hero-copy">
            <p className="farmers-page__eyebrow">Meet the growers</p>
            <h1 className="farmers-page__title">Farmer stalls</h1>
            <p className="farmers-page__subtitle">
              {ordering === 'distance' && hasLocation
                ? 'Showing stalls closest to you first'
                : 'Discover trusted stalls by name, rating, or stock'}
            </p>
          </div>
        </div>
      </section>

      <div className="farmers-page__body">
        <div className="farmers-page__toolbar">
          <div className="farmers-page__search-row">
            <div className="farmers-page__search-wrap">
              <Input
                type="search"
                value={search.value}
                onChange={search.onChange}
                onKeyDown={search.onKeyDown}
                label="Search by stall name or address"
                className="farmers-page__search-input"
              />
            </div>
            <select
              className="farmers-page__select"
              value={ordering}
              onChange={(event) => changeSort(event.target.value)}
              aria-label="Sort stalls"
            >
              {SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {query.data && total > 0 ? (
          <p className="farmers-page__count">
            {total} stall{total === 1 ? '' : 's'}
          </p>
        ) : null}

        {body}
      </div>
    </div>
  );
}
