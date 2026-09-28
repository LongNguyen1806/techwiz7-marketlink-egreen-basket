import { useState } from 'react';
import { LocateFixed } from 'lucide-react';
import { MarketCard } from '../../components/common/cards/MarketCard';
import { MarketsMap } from '../../components/common/maps/MarketsMap';
import { EmptyState } from '../../components/feedback/EmptyState';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Skeleton } from '../../components/ui/Skeleton';
import { useAddToCart } from '../../hooks/common/useAddToCart';
import { useDebouncedSearchParam } from '../../hooks/common/useDebouncedSearchParam';
import { useUrlFilters } from '../../hooks/common/useUrlFilters';
import { usePublicMarketList } from '../../hooks/queries/guest/usePublicCatalog';
import { useGeolocation } from '../../hooks/useGeolocation';
import { DAYS_OF_WEEK } from '../../utils/labels';
import '../../styles/guest/MarketsPage.css';

const FILTER_DEFAULTS = { day: 0, near: false, view: 'list' };

export default function MarketsPage() {
  const { filters, setFilters } = useUrlFilters(FILTER_DEFAULTS);
  const search = useDebouncedSearchParam('q');
  const { lat, lng, requestLocation } = useGeolocation();
  const { requireSignIn } = useAddToCart();
  const [highlightedId, setHighlightedId] = useState(null);

  const hasLocation = lat !== null && lng !== null;
  const sortByDistance = filters.near && hasLocation;
  const day = DAYS_OF_WEEK.some((item) => item.value === filters.day) ? filters.day : 0;

  const query = usePublicMarketList({
    q: search.term || undefined,
    day: day || undefined,
    lat: hasLocation ? lat : undefined,
    lng: hasLocation ? lng : undefined,
    ordering: sortByDistance ? 'distance' : 'name',
  });
  const markets = query.data?.markets ?? [];
  const total = query.data?.total ?? 0;

  const toggleNearMe = () => {
    if (filters.near) {
      setFilters({ near: false });
      return;
    }
    if (!hasLocation) requestLocation();
    setFilters({ near: true });
  };

  let list;
  if (query.isPending) {
    list = (
      <div className="markets-page__grid" aria-busy>
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="markets-page__skeleton" />
        ))}
      </div>
    );
  } else if (!query.data) {
    list = <EmptyState title="Markets couldn't be loaded" actionLabel="Try again" onAction={() => query.refetch()} />;
  } else if (markets.length === 0) {
    list = (
      <EmptyState
        title="No markets match your filters"
        description="Try another day, keyword, or clear your search."
        actionLabel={search.term || day ? 'Clear filters' : undefined}
        onAction={
          search.term || day
            ? () => {
                search.clear();
                setFilters({ day: 0 });
              }
            : undefined
        }
      />
    );
  } else {
    list = (
      <>
        <div className="markets-page__grid" aria-busy={query.isFetching}>
          {markets.map((market) => (
            <MarketCard
              key={market.id}
              market={market}
              highlighted={highlightedId === market.id}
              onHover={setHighlightedId}
              onRequireSignIn={requireSignIn}
            />
          ))}
        </div>
        {query.hasNextPage ? (
          <div className="markets-page__load-more">
            <Button variant="outline" loading={query.isFetchingNextPage} onClick={() => query.fetchNextPage()}>
              Show more markets
            </Button>
          </div>
        ) : null}
      </>
    );
  }

  return (
    <div className="markets-page">
      <section className="markets-page__hero">
        <div className="markets-page__hero-inner">
          <div className="markets-page__hero-copy">
            <p className="markets-page__eyebrow">Where freshness gathers</p>
            <h1 className="markets-page__title">Local markets</h1>
            <p className="markets-page__subtitle">
              {sortByDistance
                ? 'Nearest markets to you, ready for your next visit'
                : 'Search by name, address, or the days they open'}
            </p>
          </div>
        </div>
      </section>

      <div className="markets-page__body">
        <div className="markets-page__toolbar">
          <div className="markets-page__search-row">
            <div className="markets-page__search-wrap">
              <Input
                type="search"
                value={search.value}
                onChange={search.onChange}
                onKeyDown={search.onKeyDown}
                label="Search markets or addresses"
                className="markets-page__search-input"
              />
            </div>
            <Button
              type="button"
              variant={sortByDistance ? 'default' : 'outline'}
              aria-pressed={sortByDistance}
              onClick={toggleNearMe}
            >
              <LocateFixed aria-hidden size={16} />
              Near me
            </Button>
          </div>

          <div className="markets-page__day-list" role="group" aria-label="Open on">
            <button
              type="button"
              aria-pressed={day === 0}
              className={day === 0 ? 'markets-page__day-btn markets-page__day-btn--active' : 'markets-page__day-btn'}
              onClick={() => setFilters({ day: 0 })}
            >
              All days
            </button>
            {DAYS_OF_WEEK.map((option) => {
              const active = day === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  aria-pressed={active}
                  aria-label={option.long}
                  className={active ? 'markets-page__day-btn markets-page__day-btn--active' : 'markets-page__day-btn'}
                  onClick={() => setFilters({ day: active ? 0 : option.value })}
                >
                  {option.short}
                </button>
              );
            })}
          </div>
        </div>

        {query.data && total > 0 ? (
          <p className="markets-page__count">
            {total} market{total === 1 ? '' : 's'}
          </p>
        ) : null}

        <div className="markets-page__view-switch" role="group" aria-label="Show">
          <Button
            size="sm"
            variant={filters.view === 'map' ? 'outline' : 'default'}
            aria-pressed={filters.view !== 'map'}
            onClick={() => setFilters({ view: 'list' }, { replace: true })}
          >
            List
          </Button>
          <Button
            size="sm"
            variant={filters.view === 'map' ? 'default' : 'outline'}
            aria-pressed={filters.view === 'map'}
            onClick={() => setFilters({ view: 'map' }, { replace: true })}
          >
            Map
          </Button>
        </div>

        <div className="markets-page__split" data-view={filters.view === 'map' ? 'map' : 'list'}>
          <div className="markets-page__list-panel">{list}</div>
          <div className="markets-page__map-panel">
            <MarketsMap
              key={filters.view}
              markets={markets}
              highlightedId={highlightedId}
              className="markets-page__map"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
