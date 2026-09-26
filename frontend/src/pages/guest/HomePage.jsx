import { useState } from 'react';
import PropTypes from 'prop-types';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, LocateFixed } from 'lucide-react';
import { CategoryIcon } from '../../components/common/badges/CategoryIcon';
import { FarmerCard } from '../../components/common/cards/FarmerCard';
import { MarketCard } from '../../components/common/cards/MarketCard';
import { ProductCard } from '../../components/common/cards/ProductCard';
import { EmptyState } from '../../components/feedback/EmptyState';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Skeleton } from '../../components/ui/Skeleton';
import { useAddToCart } from '../../hooks/common/useAddToCart';
import { useGeolocation } from '../../hooks/useGeolocation';
import {
  useCategories,
  usePublicFarmers,
  usePublicMarkets,
  usePublicProducts,
} from '../../hooks/queries/guest/usePublicCatalog';
import '../../styles/guest/HomePage.css';

const HERO_VIDEO = '/banner.mp4';


const MARKETS_PATH = '/markets';
const PRODUCTS_PATH = '/products';
const FARMERS_PATH = '/farmers';


const MARKETS_SHOWN = 3;
const PRODUCTS_SHOWN = 8;
const FARMERS_SHOWN = 4;
const PRODUCT_PARAMS = { ordering: 'rating', page_size: 10 };
const FARMER_PARAMS = { ordering: 'rating', page_size: 5 };

const STEPS = [
  { title: 'Discover', desc: 'Explore nearby markets, trusted stalls, and seasonal produce' },
  { title: 'Pre-order', desc: 'Reserve what you need — your selection is held at the stall' },
  { title: 'Choose a slot', desc: 'Pick a convenient pickup window that fits your day' },
  { title: 'Collect & pay', desc: 'Arrive on time, pay at the stall, and leave with peak-fresh produce' },
];

function SectionHeading({ title, description, href, linkLabel = 'View all' }) {
  return (
    <div className="home-page__section-heading">
      <div className="home-page__section-copy">
        <h2 className="home-page__section-title">{title}</h2>
        <p className="home-page__section-desc">{description}</p>
      </div>
      <Button asChild variant="ghost" className="home-page__section-link">
        <Link to={href}>
          {linkLabel}
          <span className="home-page__section-link-icon">
            <ArrowRight className="home-page__section-link-arrow" aria-hidden />
          </span>
        </Link>
      </Button>
    </div>
  );
}

SectionHeading.propTypes = {
  title: PropTypes.string.isRequired,
  description: PropTypes.string.isRequired,
  href: PropTypes.string.isRequired,
  linkLabel: PropTypes.string,
};


function CardGrid({ query, shown, gridClass, skeletonClass, errorTitle, emptyTitle, renderItem }) {
  if (query.isPending) {
    return (
      <div className={gridClass} aria-busy>
        {Array.from({ length: shown }).map((_, index) => (
          <Skeleton key={index} className={skeletonClass} />
        ))}
      </div>
    );
  }
  if (!query.data) {
    return <EmptyState title={errorTitle} actionLabel="Try again" onAction={() => query.refetch()} />;
  }
  const items = query.data.results.slice(0, shown);
  if (items.length === 0) return <EmptyState title={emptyTitle} />;
  return <div className={gridClass}>{items.map(renderItem)}</div>;
}

CardGrid.propTypes = {
  query: PropTypes.object.isRequired,
  shown: PropTypes.number.isRequired,
  gridClass: PropTypes.string.isRequired,
  skeletonClass: PropTypes.string.isRequired,
  errorTitle: PropTypes.string.isRequired,
  emptyTitle: PropTypes.string.isRequired,
  renderItem: PropTypes.func.isRequired,
};

export default function HomePage() {
  const navigate = useNavigate();
  const { addToCart, requireSignIn } = useAddToCart();
  const [term, setTerm] = useState('');
  const { lat, lng, requestLocation } = useGeolocation();
  const hasLocation = lat !== null && lng !== null;

  const categoriesQuery = useCategories();
  
  const marketsQuery = usePublicMarkets(
    hasLocation ? { lat, lng, ordering: 'distance', page_size: 5 } : { ordering: 'name', page_size: 5 },
  );
  const productsQuery = usePublicProducts(PRODUCT_PARAMS);
  const farmersQuery = usePublicFarmers(FARMER_PARAMS);

  
  const onSearch = (event) => {
    event.preventDefault();
    const query = term.trim();
    navigate(query ? `${PRODUCTS_PATH}?q=${encodeURIComponent(query)}` : PRODUCTS_PATH);
  };

  return (
    <div className="home-page">
      <section className="home-page__hero">
        <video className="home-page__hero-video" autoPlay muted loop playsInline preload="auto" aria-hidden>
          <source src={HERO_VIDEO} type="video/mp4" />
        </video>
        <div className="home-page__hero-overlay-a" aria-hidden />
        <div className="home-page__hero-overlay-b" aria-hidden />

        <div className="home-page__hero-inner">
          <div className="home-page__hero-copy">
            <p className="home-page__eyebrow">MarketLink</p>
            <h1 className="home-page__title">Local markets, reserved for you</h1>
            <p className="home-page__intro">
              Pre-order from trusted stalls, pick up on your schedule, and pay when you collect — no delivery fees,
              just fresher produce.
            </p>

            <form className="home-page__search" role="search" onSubmit={onSearch}>
              <Input
                id="home-search"
                type="search"
                value={term}
                onChange={(event) => setTerm(event.target.value)}
                label="Search produce, stalls, or markets"
                className="home-page__search-input"
              />
              <Button type="submit" variant="accent" className="home-page__search-submit">
                Search
              </Button>
            </form>

            <div className="home-page__hero-actions">
              <Button type="button" variant="outline" className="home-page__hero-btn" onClick={requestLocation}>
                <LocateFixed className="home-page__icon-sm" aria-hidden />
                {hasLocation ? 'Update my location' : 'Use my location'}
              </Button>
              <Button asChild variant="outline" className="home-page__hero-btn">
                <Link to={MARKETS_PATH}>
                  Browse all markets
                  <ArrowRight className="home-page__icon-sm" aria-hidden />
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </section>

      <section className="home-page__categories">
        <div className="home-page__categories-inner">
          <div className="home-page__categories-head">
            <h2 className="home-page__categories-title">Shop by category</h2>
            <p className="home-page__categories-hint">From greens to dairy — find today&apos;s freshest picks</p>
          </div>
          <div className="home-page__categories-scroll">
            {categoriesQuery.isPending
              ? Array.from({ length: 6 }).map((_, index) => (
                  <Skeleton key={index} className="home-page__category-skeleton" />
                ))
              : (categoriesQuery.data ?? []).map((category) => (
                  <Link
                    key={category.id}
                    to={`${PRODUCTS_PATH}?category=${category.id}`}
                    className="home-page__category-card"
                  >
                    <span className="home-page__category-icon-wrap">
                      <CategoryIcon icon={category.icon} className="home-page__category-icon" />
                    </span>
                    <span className="home-page__category-name">{category.name}</span>
                  </Link>
                ))}
          </div>
        </div>
      </section>

      <section className="home-page__section">
        <SectionHeading
          title="Markets near you"
          description={
            hasLocation
              ? 'Closest markets to where you are right now'
              : 'Share your location to see the nearest markets first'
          }
          href={MARKETS_PATH}
          linkLabel="See all markets"
        />
        <CardGrid
          query={marketsQuery}
          shown={MARKETS_SHOWN}
          gridClass="home-page__grid-markets"
          skeletonClass="home-page__skeleton-market"
          errorTitle="Markets couldn't be loaded"
          emptyTitle="No markets are open yet"
          renderItem={(market) => <MarketCard key={market.id} market={market} onRequireSignIn={requireSignIn} />}
        />
      </section>

      <section className="home-page__section--highlight">
        <div className="home-page__section-inner">
          <SectionHeading
            title="Today's standouts"
            description="Top-rated produce, ready to pre-order and pick up"
            href={PRODUCTS_PATH}
            linkLabel="Browse all produce"
          />
          <CardGrid
            query={productsQuery}
            shown={PRODUCTS_SHOWN}
            gridClass="home-page__grid-products"
            skeletonClass="home-page__skeleton-product"
            errorTitle="Products couldn't be loaded"
            emptyTitle="No produce listed yet"
            renderItem={(product) => (
              <ProductCard
                key={product.id}
                product={product}
                onAddToCart={addToCart}
                onRequireSignIn={requireSignIn}
              />
            )}
          />
        </div>
      </section>

      <section className="home-page__section">
        <SectionHeading
          title="Stalls worth knowing"
          description="Meet highly rated farmers before you place your order"
          href={FARMERS_PATH}
          linkLabel="Browse all stalls"
        />
        <CardGrid
          query={farmersQuery}
          shown={FARMERS_SHOWN}
          gridClass="home-page__grid-farmers"
          skeletonClass="home-page__skeleton-farmer"
          errorTitle="Stalls couldn't be loaded"
          emptyTitle="No stalls to show yet"
          renderItem={(farmer) => <FarmerCard key={farmer.id} farmer={farmer} onRequireSignIn={requireSignIn} />}
        />
      </section>

      <section className="home-page__how">
        <div className="home-page__how-inner">
          <div className="home-page__how-intro">
            <p className="home-page__how-eyebrow">How MarketLink works</p>
            <h2 className="home-page__how-title">From browse to bag in four steps</h2>
            <p className="home-page__how-desc">
              Reserve ahead, skip the guesswork, and walk out with produce waiting for you.
            </p>
          </div>

          <ol className="home-page__steps">
            {STEPS.map((step, index) => (
              <li key={step.title} className="home-page__step">
                <span className="home-page__step-num">{String(index + 1).padStart(2, '0')}</span>
                <h3 className="home-page__step-title">{step.title}</h3>
                <p className="home-page__step-desc">{step.desc}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="home-page__cta">
        <div className="home-page__cta-bg" aria-hidden />
        <div className="home-page__cta-blob-a" aria-hidden />
        <div className="home-page__cta-blob-b" aria-hidden />
        <div className="home-page__cta-inner">
          <div className="home-page__cta-copy">
            <p className="home-page__cta-title">Your next market run starts here</p>
            <p className="home-page__cta-desc">
              Find a nearby market, choose a stall you trust, and lock in your pre-order in minutes.
            </p>
          </div>
          <div className="home-page__cta-actions">
            <Button asChild size="lg" variant="accent" className="home-page__cta-btn">
              <Link to={MARKETS_PATH}>Explore markets</Link>
            </Button>
            <Button asChild size="lg" variant="outline" className="home-page__cta-btn home-page__cta-outline">
              <Link to={PRODUCTS_PATH}>Shop produce</Link>
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}
