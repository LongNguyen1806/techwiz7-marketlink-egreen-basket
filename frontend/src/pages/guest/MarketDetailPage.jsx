import { Link, useNavigate, useParams } from 'react-router-dom';
import PropTypes from 'prop-types';
import { ArrowLeft, CalendarX2, Clock3, ExternalLink, MapPin, Navigation, Store } from 'lucide-react';
import { LazyImage } from '../../components/common/LazyImage';
import { FarmerCard } from '../../components/common/cards/FarmerCard';
import { FavoriteButton } from '../../components/common/favorites/FavoriteButton';
import { MiniMap } from '../../components/common/maps/MarketsMap';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Skeleton } from '../../components/ui/Skeleton';
import { useAddToCart } from '../../hooks/common/useAddToCart';
import { useUrlFilters } from '../../hooks/common/useUrlFilters';
import { usePublicMarket, usePublicMarketFarmers } from '../../hooks/queries/guest/usePublicCatalog';
import { useGeolocation } from '../../hooks/useGeolocation';
import { formatDate } from '../../utils/formatters';
import { googleMapsDirectionsUrl } from '../../utils/helpers/geo';
import { DAYS_OF_WEEK, dayOfWeekLabel } from '../../utils/labels';
import '../../styles/guest/MarketDetailPage.css';

function MetaChip({ icon, label }) {
  return (
    <span className="market-detail-page__meta-chip">
      <span className="market-detail-page__meta-chip-icon">{icon}</span>
      {label}
    </span>
  );
}

MetaChip.propTypes = { icon: PropTypes.node.isRequired, label: PropTypes.string.isRequired };

function closureLabel(closure) {
  const range =
    closure.start_date === closure.end_date
      ? formatDate(closure.start_date)
      : `${formatDate(closure.start_date)} – ${formatDate(closure.end_date)}`;
  return closure.reason ? `Closed ${range} · ${closure.reason}` : `Closed ${range}`;
}

/** Stalls selling here (G-03), filtered by the day the shopper plans to come. */
function MarketFarmers({ market, onRequireSignIn }) {
  const { filters, setFilters } = useUrlFilters({ day: 0 });
  const day = market.operating_days.includes(filters.day) ? filters.day : 0;
  const farmersQuery = usePublicMarketFarmers(market.id, { day: day || undefined });
  const farmers = farmersQuery.data?.farmers ?? [];
  const total = farmersQuery.data?.total ?? 0;

  let body;
  if (farmersQuery.isPending) {
    body = (
      <div className="market-detail-page__farmers-grid" aria-busy>
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="market-detail-page__farmer-skeleton" />
        ))}
      </div>
    );
  } else if (!farmersQuery.data) {
    body = (
      <EmptyState title="Stalls couldn't be loaded" actionLabel="Try again" onAction={() => farmersQuery.refetch()} />
    );
  } else if (farmers.length === 0) {
    body = (
      <EmptyState
        title={day ? `No stalls here on ${dayOfWeekLabel(day)}` : 'No stalls are listed at this market yet'}
        actionLabel={day ? 'Show every day' : undefined}
        onAction={day ? () => setFilters({ day: 0 }) : undefined}
      />
    );
  } else {
    body = (
      <>
        <div className="market-detail-page__farmers-grid" aria-busy={farmersQuery.isFetching}>
          {farmers.map((farmer) => {
            const here = farmer.markets?.find((entry) => entry.market_id === market.id);
            return (
              <div key={farmer.id} className="market-detail-page__farmer-item">
                <FarmerCard farmer={farmer} onRequireSignIn={onRequireSignIn} />
                {here?.stall_label ? (
                  <p className="market-detail-page__stall-note">
                    Stall location: <strong>{here.stall_label}</strong>
                  </p>
                ) : null}
              </div>
            );
          })}
        </div>
        {farmersQuery.hasNextPage ? (
          <div className="page-primitive__justify-center-row">
            <Button
              variant="outline"
              loading={farmersQuery.isFetchingNextPage}
              onClick={() => farmersQuery.fetchNextPage()}
            >
              Show more stalls
            </Button>
          </div>
        ) : null}
      </>
    );
  }

  return (
    <section className="market-detail-page__farmers">
      <div className="market-detail-page__farmers-head">
        <div>
          <h2 className="market-detail-page__farmers-title">Stalls at this market</h2>
          <p className="market-detail-page__farmers-desc">Growers currently selling at {market.name}</p>
        </div>
        {farmersQuery.data ? (
          <p className="market-detail-page__farmers-count">
            {total} stall{total === 1 ? '' : 's'}
          </p>
        ) : null}
      </div>

      <div className="page-primitive__actions-row" role="group" aria-label="Show stalls open on">
        <Button size="sm" variant={day === 0 ? 'default' : 'outline'} aria-pressed={day === 0} onClick={() => setFilters({ day: 0 })}>
          Any day
        </Button>
        {DAYS_OF_WEEK.filter((option) => market.operating_days.includes(option.value)).map((option) => (
          <Button
            key={option.value}
            size="sm"
            variant={day === option.value ? 'default' : 'outline'}
            aria-pressed={day === option.value}
            aria-label={option.long}
            onClick={() => setFilters({ day: day === option.value ? 0 : option.value })}
          >
            {option.short}
          </Button>
        ))}
      </div>

      {body}
    </section>
  );
}

MarketFarmers.propTypes = {
  market: PropTypes.object.isRequired,
  onRequireSignIn: PropTypes.func.isRequired,
};

export default function MarketDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { lat, lng } = useGeolocation();
  // With the shopper's location the backend also returns distance_km.
  const coords = lat !== null && lng !== null ? { lat, lng } : {};
  const marketQuery = usePublicMarket(id, coords);
  const { requireSignIn } = useAddToCart();

  if (marketQuery.isPending && marketQuery.fetchStatus !== 'idle') return <PageSkeleton />;
  if (!marketQuery.data) {
    const notFound = !marketQuery.isError || marketQuery.error?.status === 404;
    return (
      <div className="market-detail-page__empty-wrap">
        {notFound ? (
          <EmptyState
            title="This market could not be found"
            description="It may have closed, or the link is out of date."
            actionLabel="Browse markets"
            onAction={() => navigate('/markets')}
          />
        ) : (
          <EmptyState title="This market couldn't be loaded" actionLabel="Try again" onAction={() => marketQuery.refetch()} />
        )}
      </div>
    );
  }

  const market = marketQuery.data;
  const hasPoint = typeof market.latitude === 'number' && typeof market.longitude === 'number';

  return (
    <div className="market-detail-page">
      <section className="market-detail-page__banner">
        <LazyImage src={market.image ?? ''} alt={market.name} className="market-detail-page__banner-img" />
        <div className="market-detail-page__banner-overlay-a" aria-hidden />
        <div className="market-detail-page__banner-overlay-b" aria-hidden />

        <div className="market-detail-page__banner-inner">
          <Link to="/markets" className="market-detail-page__back">
            <ArrowLeft className="market-detail-page__back-icon" aria-hidden />
            Back to markets
          </Link>

          <div className="market-detail-page__banner-head">
            <div className="market-detail-page__banner-copy">
              <h1 className="market-detail-page__title">{market.name}</h1>
              <p className="market-detail-page__address">
                <MapPin className="market-detail-page__address-icon" strokeWidth={1.75} aria-hidden />
                <span>{market.address}</span>
              </p>
            </div>
            <FavoriteButton
              kind="markets"
              id={market.id}
              isFavorite={Boolean(market.is_favorite)}
              onRequireSignIn={requireSignIn}
              className="market-detail-page__fav-btn"
            />
          </div>
        </div>
      </section>

      <div className="market-detail-page__body">
        <div className="market-detail-page__meta-row">
          <MetaChip icon={<Clock3 strokeWidth={1.75} aria-hidden />} label={`${market.open_time}–${market.close_time}`} />
          {typeof market.distance_km === 'number' ? (
            <MetaChip icon={<Navigation strokeWidth={1.75} aria-hidden />} label={`${market.distance_km.toFixed(1)} km`} />
          ) : null}
          <MetaChip
            icon={<Store strokeWidth={1.75} aria-hidden />}
            label={`${market.farmer_count} stall${market.farmer_count === 1 ? '' : 's'}`}
          />
        </div>

        {/* D-023: planned closures inside the booking horizon. */}
        {market.upcoming_closures?.length ? (
          <div className="page-primitive__warn-banner" role="note">
            {market.upcoming_closures.map((closure) => (
              <p key={`${closure.start_date}-${closure.end_date}`}>
                <CalendarX2 size={16} aria-hidden /> {closureLabel(closure)}
              </p>
            ))}
          </div>
        ) : null}

        <div className="market-detail-page__split">
          <div className="market-detail-page__about">
            {market.description ? (
              <div>
                <h2 className="market-detail-page__section-title">About the market</h2>
                <p className="market-detail-page__description">{market.description}</p>
              </div>
            ) : null}

            <div>
              <p className="market-detail-page__days-label">Open on</p>
              <div className="market-detail-page__days">
                {market.operating_days.map((day) => (
                  <Badge key={day} variant="secondary" className="market-detail-page__day-badge">
                    {dayOfWeekLabel(day)}
                  </Badge>
                ))}
              </div>
            </div>

            <div className="market-detail-page__actions">
              {hasPoint ? (
                <Button asChild size="lg" className="market-detail-page__btn-press">
                  <a href={googleMapsDirectionsUrl(market.latitude, market.longitude)} target="_blank" rel="noreferrer">
                    <ExternalLink className="market-detail-page__action-icon" aria-hidden />
                    Get directions
                  </a>
                </Button>
              ) : null}
              <Button asChild size="lg" variant="secondary" className="market-detail-page__btn-press">
                <Link to={`/products?market_id=${market.id}`}>Shop produce here</Link>
              </Button>
            </div>
          </div>

          {hasPoint ? (
            <div className="market-detail-page__map-col">
              <h2 className="market-detail-page__map-title">On the map</h2>
              <MiniMap
                latitude={market.latitude}
                longitude={market.longitude}
                label={market.name}
                className="market-detail-page__map"
              />
            </div>
          ) : null}
        </div>

        <MarketFarmers market={market} onRequireSignIn={requireSignIn} />
      </div>
    </div>
  );
}
