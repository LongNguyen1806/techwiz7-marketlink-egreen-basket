import { Link, useNavigate, useParams } from 'react-router-dom';
import PropTypes from 'prop-types';
import { CalendarX2, ExternalLink } from 'lucide-react';
import { LazyImage } from '../../components/common/LazyImage';
import { RatingStars } from '../../components/common/RatingStars';
import { ProductCard } from '../../components/common/cards/ProductCard';
import { ProductCardSkeletonGrid } from '../../components/common/cards/ProductCardSkeleton';
import { FavoriteButton } from '../../components/common/favorites/FavoriteButton';
import { MiniMap } from '../../components/common/maps/MarketsMap';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/Avatar';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Skeleton } from '../../components/ui/Skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/Tabs';
import { useAddToCart } from '../../hooks/common/useAddToCart';
import { useUrlFilters } from '../../hooks/common/useUrlFilters';
import { usePickupOptions } from '../../hooks/queries/customer/usePickupOptions';
import {
  usePublicFarmer,
  usePublicFarmerReviews,
  usePublicProductList,
} from '../../hooks/queries/guest/usePublicCatalog';
import { useGeolocation } from '../../hooks/useGeolocation';
import { formatDate, formatDateTime } from '../../utils/formatters';
import { googleMapsDirectionsUrl } from '../../utils/helpers/geo';
import { dayOfWeekLabel } from '../../utils/labels';
import '../../styles/guest/FarmerDetailPage.css';

const TABS = ['products', 'reviews', 'about', 'schedule'];

const hhmm = (time) => (typeof time === 'string' ? time.slice(0, 5) : time);

function closureLabel(closure) {
  const range =
    closure.start_date === closure.end_date
      ? formatDate(closure.start_date)
      : `${formatDate(closure.start_date)} – ${formatDate(closure.end_date)}`;
  return closure.reason ? `Closed ${range} · ${closure.reason}` : `Closed ${range}`;
}

function StallProducts({ farmerId, onAddToCart, onRequireSignIn }) {
  const query = usePublicProductList({ farmer_id: farmerId });
  const products = query.data?.products ?? [];

  if (query.isPending) return <ProductCardSkeletonGrid count={3} className="farmer-detail-page__products-grid" />;
  if (!query.data) {
    return <EmptyState title="Products couldn't be loaded" actionLabel="Try again" onAction={() => query.refetch()} />;
  }
  if (products.length === 0) return <EmptyState title="Nothing listed yet — check back soon" />;

  return (
    <>
      <div className="farmer-detail-page__products-grid">
        {products.map((product) => (
          <ProductCard key={product.id} product={product} onAddToCart={onAddToCart} onRequireSignIn={onRequireSignIn} />
        ))}
      </div>
      {query.hasNextPage ? (
        <div className="page-primitive__justify-center-row">
          <Button variant="outline" loading={query.isFetchingNextPage} onClick={() => query.fetchNextPage()}>
            Show more products
          </Button>
        </div>
      ) : null}
    </>
  );
}

StallProducts.propTypes = {
  farmerId: PropTypes.number.isRequired,
  onAddToCart: PropTypes.func.isRequired,
  onRequireSignIn: PropTypes.func.isRequired,
};

function StallReviews({ farmerId }) {
  const query = usePublicFarmerReviews(farmerId);
  const reviews = query.data?.reviews ?? [];

  if (query.isPending) return <p className="farmer-detail-page__no-reviews">Loading reviews…</p>;
  if (!query.data) {
    return <EmptyState title="Reviews couldn't be loaded" actionLabel="Try again" onAction={() => query.refetch()} />;
  }
  if (reviews.length === 0) {
    return <p className="farmer-detail-page__no-reviews">No reviews yet — be the first to share your experience.</p>;
  }

  return (
    <>
      {reviews.map((review) => (
        <div key={review.id} className="farmer-detail-page__review">
          <div className="farmer-detail-page__review-head">
            <p className="farmer-detail-page__review-author">{review.customer_display_name}</p>
            <RatingStars value={review.rating} />
          </div>
          {review.comment ? <p className="farmer-detail-page__review-body">{review.comment}</p> : null}
          <p className="farmer-detail-page__review-date">{formatDate(review.created_at)}</p>
          {review.reply ? (
            <div className="farmer-detail-page__reply">
              <p className="farmer-detail-page__reply-title">Reply from the stall</p>
              <p className="farmer-detail-page__reply-body">{review.reply}</p>
            </div>
          ) : null}
        </div>
      ))}
      {query.hasNextPage ? (
        <div className="page-primitive__justify-center-row">
          <Button variant="outline" loading={query.isFetchingNextPage} onClick={() => query.fetchNextPage()}>
            Show more reviews
          </Button>
        </div>
      ) : null}
    </>
  );
}

StallReviews.propTypes = { farmerId: PropTypes.number.isRequired };

function StallAbout({ farmer }) {
  const primaryWindow = farmer.pickup_windows?.find(
    (window) => typeof window.latitude === 'number' && typeof window.longitude === 'number',
  );

  return (
    <div className="farmer-detail-page__about-layout">
      <div className="farmer-detail-page__about-copy">
        {farmer.description ? <p className="farmer-detail-page__bio">{farmer.description}</p> : null}
        {farmer.phone ? (
          <p className="farmer-detail-page__phone">
            Phone:{' '}
            <a className="farmer-detail-page__phone-link" href={`tel:${farmer.phone}`}>
              {farmer.phone}
            </a>
          </p>
        ) : null}
        {farmer.order_cutoff_hours ? (
          <p className="farmer-detail-page__phone">
            Orders close {farmer.order_cutoff_hours} hour{farmer.order_cutoff_hours === 1 ? '' : 's'} before each
            pickup slot.
          </p>
        ) : null}
        <div className="farmer-detail-page__market-links">
          {farmer.markets.map((market) => (
            <Button key={market.market_id} asChild variant="outline" size="sm">
              <Link to={`/markets/${market.market_id}`}>{market.market_name}</Link>
            </Button>
          ))}
        </div>
      </div>

      <div className="farmer-detail-page__about-map">
        {primaryWindow ? (
          <>
            <MiniMap
              latitude={primaryWindow.latitude}
              longitude={primaryWindow.longitude}
              label={`${farmer.stall_name} · ${primaryWindow.market_name}`}
              className="farmer-detail-page__map"
            />
            <Button asChild variant="outline" className="farmer-detail-page__directions">
              <a
                href={googleMapsDirectionsUrl(primaryWindow.latitude, primaryWindow.longitude)}
                target="_blank"
                rel="noreferrer"
              >
                <ExternalLink className="farmer-detail-page__directions-icon" aria-hidden />
                Get directions to the stall
              </a>
            </Button>
          </>
        ) : null}
      </div>
    </div>
  );
}

StallAbout.propTypes = { farmer: PropTypes.object.isRequired };

/** Bookable slots over the booking horizon (same data the checkout uses). */
function StallSchedule({ farmerId }) {
  const query = usePickupOptions(farmerId);

  if (query.isPending) {
    return (
      <div className="farmer-detail-page__schedule-list" aria-busy>
        <Skeleton className="farmer-detail-page__product-skeleton" />
      </div>
    );
  }
  if (!query.data) {
    return <EmptyState title="Pickup times couldn't be loaded" actionLabel="Try again" onAction={() => query.refetch()} />;
  }

  const options = query.data
    .map((option) => ({
      ...option,
      dates: option.dates
        .map((date) => ({ ...date, slots: date.slots.filter((slot) => slot.is_bookable) }))
        .filter((date) => date.slots.length > 0),
    }))
    .filter((option) => option.dates.length > 0);

  if (options.length === 0) return <EmptyState title="No pickup times are open right now" />;

  return (
    <div className="farmer-detail-page__schedule-list">
      {options.map((option) => (
        <div key={option.market_id} className="farmer-detail-page__schedule-card">
          <div>
            <h3 className="farmer-detail-page__schedule-market">{option.market_name}</h3>
            {option.stall_label ? <p className="farmer-detail-page__schedule-stall">{option.stall_label}</p> : null}
          </div>
          <div className="farmer-detail-page__schedule-dates">
            {option.dates.map((date) => (
              <div key={date.date}>
                <p className="farmer-detail-page__date-label">
                  {dayOfWeekLabel(date.day_of_week)} · {formatDate(date.date)}
                </p>
                <div className="farmer-detail-page__slots">
                  {date.slots.map((slot) => (
                    <div key={slot.pickup_slot_id} className="farmer-detail-page__slot">
                      <p className="farmer-detail-page__slot-time">
                        {hhmm(slot.start_time)}–{hhmm(slot.end_time)}
                      </p>
                      <p className="farmer-detail-page__slot-cutoff">Order by {formatDateTime(slot.cutoff_at)}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

StallSchedule.propTypes = { farmerId: PropTypes.number.isRequired };

export default function FarmerDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { lat, lng } = useGeolocation();
  // With the shopper's location the backend also returns distance_km.
  const coords = lat !== null && lng !== null ? { lat, lng } : {};
  const farmerQuery = usePublicFarmer(id, coords);
  const { filters, setFilters } = useUrlFilters({ tab: 'products' });
  const { addToCart, requireSignIn } = useAddToCart();

  if (farmerQuery.isPending && farmerQuery.fetchStatus !== 'idle') return <PageSkeleton />;
  if (!farmerQuery.data) {
    const notFound = !farmerQuery.isError || farmerQuery.error?.status === 404;
    return (
      <div className="farmer-detail-page__empty-wrap">
        {notFound ? (
          <EmptyState
            title="This stall could not be found"
            description="It may no longer be selling on MarketLink, or the link is out of date."
            actionLabel="Browse stalls"
            onAction={() => navigate('/farmers')}
          />
        ) : (
          <EmptyState title="This stall couldn't be loaded" actionLabel="Try again" onAction={() => farmerQuery.refetch()} />
        )}
      </div>
    );
  }

  const farmer = farmerQuery.data;
  const tab = TABS.includes(filters.tab) ? filters.tab : 'products';

  return (
    <div className="farmer-detail-page">
      <div className="farmer-detail-page__cover">
        {farmer.image ? <LazyImage src={farmer.image} alt="" className="farmer-detail-page__cover-img" /> : null}
        <div className="farmer-detail-page__cover-gradient" aria-hidden />
      </div>

      <div className="farmer-detail-page__container">
        <div className="farmer-detail-page__profile-row">
          <div className="farmer-detail-page__profile-main">
            <Avatar className="farmer-detail-page__avatar">
              {farmer.image ? <AvatarImage src={farmer.image} alt="" /> : null}
              <AvatarFallback className="farmer-detail-page__avatar-fallback">
                {farmer.stall_name.slice(0, 2).toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <div className="farmer-detail-page__profile-copy">
              <h1 className="farmer-detail-page__name">{farmer.stall_name}</h1>
              {farmer.contact_person ? <p className="farmer-detail-page__contact">{farmer.contact_person}</p> : null}
              <div className="farmer-detail-page__rating-wrap">
                <RatingStars value={farmer.rating_avg} count={farmer.rating_count} size="md" />
                {typeof farmer.distance_km === 'number' ? (
                  <Badge variant="secondary">{farmer.distance_km.toFixed(1)} km</Badge>
                ) : null}
              </div>
            </div>
          </div>
          <FavoriteButton
            kind="farmers"
            id={farmer.id}
            isFavorite={Boolean(farmer.is_favorite)}
            onRequireSignIn={requireSignIn}
            className="farmer-detail-page__fav"
          />
        </div>

        <div className="farmer-detail-page__badges">
          {farmer.markets.map((market) => (
            <Badge key={market.market_id} variant="secondary">
              {market.stall_label ? `${market.market_name} · ${market.stall_label}` : market.market_name}
            </Badge>
          ))}
          {farmer.operating_days?.length ? (
            <Badge variant="outline">Sells on {farmer.operating_days.map(dayOfWeekLabel).join(', ')}</Badge>
          ) : null}
        </div>

        {/* D-023: the stall's own planned days off inside the booking horizon. */}
        {farmer.upcoming_closures?.length ? (
          <div className="page-primitive__warn-banner" role="note">
            {farmer.upcoming_closures.map((closure) => (
              <p key={`${closure.start_date}-${closure.end_date}`}>
                <CalendarX2 size={16} aria-hidden /> {closureLabel(closure)}
              </p>
            ))}
          </div>
        ) : null}

        <Tabs
          value={tab}
          onValueChange={(value) => setFilters({ tab: value }, { replace: true })}
          className="farmer-detail-page__tabs"
        >
          <TabsList>
            <TabsTrigger value="products">On the stall ({farmer.in_stock_product_count ?? 0})</TabsTrigger>
            <TabsTrigger value="reviews">Reviews ({farmer.rating_count ?? 0})</TabsTrigger>
            <TabsTrigger value="about">About the stall</TabsTrigger>
            <TabsTrigger value="schedule">Pickup times</TabsTrigger>
          </TabsList>

          <TabsContent value="products">
            <StallProducts farmerId={farmer.id} onAddToCart={addToCart} onRequireSignIn={requireSignIn} />
          </TabsContent>
          <TabsContent value="reviews" className="farmer-detail-page__reviews-panel">
            <StallReviews farmerId={farmer.id} />
          </TabsContent>
          <TabsContent value="about">
            <StallAbout farmer={farmer} />
          </TabsContent>
          <TabsContent value="schedule">
            <StallSchedule farmerId={farmer.id} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
