import { Link } from 'react-router-dom';
import { CalendarCheck, HandCoins, Leaf, MapPin, Search, ShieldCheck, Sprout, Store } from 'lucide-react';

import { Accordion } from '../../components/common/Accordion';
import { Button } from '../../components/ui/Button';
import { ROUTES } from '../../constants/routes';
import { DEFAULT_BOOKING_HORIZON_DAYS, TEAM, VALUES, faq, howItWorks } from '../../constants/siteContent';
import { useScrollToHash } from '../../hooks/common/useScrollToHash';
import {
  usePublicConfig,
  usePublicFarmers,
  usePublicMarkets,
  usePublicProducts,
} from '../../hooks/queries/guest/usePublicCatalog';
import '../../styles/guest/StaticPages.css';

const STEP_ICONS = [Search, CalendarCheck, MapPin];
const VALUE_ICONS = [Leaf, Sprout, ShieldCheck, HandCoins];
const COUNT_ONLY = { page_size: 1 };

function initials(name) {
  return name
    .split(' ')
    .filter(Boolean)
    .map((part) => part[0])
    .slice(-2)
    .join('')
    .toUpperCase();
}

function LiveFigure({ value, label }) {
  return (
    <div className="static-page__stat">
      <span className="static-page__stat-value">{value ?? '—'}</span>
      <span className="static-page__stat-label">{label}</span>
    </div>
  );
}

export default function AboutPage() {
  const configQuery = usePublicConfig();
  const horizonDays = configQuery.data?.booking_horizon_days ?? DEFAULT_BOOKING_HORIZON_DAYS;
  const markets = usePublicMarkets(COUNT_ONLY).data?.count;
  const stalls = usePublicFarmers(COUNT_ONLY).data?.count;
  const products = usePublicProducts(COUNT_ONLY).data?.count;

  const hash = useScrollToHash();
  const openFaq = hash.startsWith('faq-') ? hash.slice(4) : null;

  return (
    <div className="static-page">
      <section className="static-page__hero">
        <div className="static-page__hero-inner">
          <div className="static-page__hero-copy">
            <p className="static-page__eyebrow">About MarketLink</p>
            <h1 className="static-page__title">Local markets, reserved for you</h1>
            <p className="static-page__lead">
              MarketLink connects shoppers with the farmers they meet at the market. Reserve fresh produce ahead,
              pick it up at the stall on your schedule, and pay when you collect.
            </p>
            <div className="static-page__stats" aria-label="MarketLink today">
              <LiveFigure value={markets} label="markets" />
              <LiveFigure value={stalls} label="farmer stalls" />
              <LiveFigure value={products} label="products on sale" />
            </div>
          </div>
        </div>
      </section>

      <div className="static-page__body">
        <section className="static-page__section" aria-labelledby="about-mission">
          <h2 className="static-page__section-title" id="about-mission">
            Our mission
          </h2>
          <p className="static-page__prose">
            Local farmers grow some of the best food in the city, but selling it depends on who walks past the stall
            that morning. Shoppers want that food without arriving at dawn to find it gone. MarketLink sits between
            the two: shoppers reserve what they want, farmers bring what has been reserved, and less goes to waste.
          </p>
        </section>

        <section className="static-page__section" aria-labelledby="about-how">
          <h2 className="static-page__section-title" id="about-how">
            How it works
          </h2>
          <div className="static-page__cards static-page__cards--3">
            {howItWorks(horizonDays).map((step, index) => {
              const Icon = STEP_ICONS[index];
              return (
                <article key={step.title} className="static-page__card">
                  <span className="static-page__step-number">{index + 1}</span>
                  <h3 className="static-page__card-title">
                    <Icon aria-hidden size={18} /> {step.title}
                  </h3>
                  <p className="static-page__card-text">{step.text}</p>
                </article>
              );
            })}
          </div>
        </section>

        <section className="static-page__section" aria-labelledby="about-why">
          <h2 className="static-page__section-title" id="about-why">
            Why MarketLink
          </h2>
          <div className="static-page__cards static-page__cards--4">
            {VALUES.map((value, index) => {
              const Icon = VALUE_ICONS[index];
              return (
                <article key={value.title} className="static-page__card">
                  <span className="static-page__card-icon">
                    <Icon aria-hidden />
                  </span>
                  <h3 className="static-page__card-title">{value.title}</h3>
                  <p className="static-page__card-text">{value.text}</p>
                </article>
              );
            })}
          </div>
        </section>

        <section className="static-page__band" aria-labelledby="about-sellers">
          <div>
            <h2 className="static-page__band-title" id="about-sellers">
              Sell at the market, and sell ahead of it
            </h2>
            <p className="static-page__band-text">
              Know what is reserved before market day, set your own pickup slots and limits, and meet the same
              regulars every week.
            </p>
          </div>
          <Button asChild variant="secondary">
            <Link to={ROUTES.REGISTER_FARMER}>
              <Store aria-hidden size={16} /> Become a seller
            </Link>
          </Button>
        </section>

        <section className="static-page__section" aria-labelledby="about-team">
          <h2 className="static-page__section-title" id="about-team">
            The team
          </h2>
          <p className="static-page__section-lead">The people who designed and built MarketLink.</p>
          <div className="static-page__cards static-page__cards--3">
            {TEAM.map((member) => (
              <article key={member.name} className="static-page__card">
                <span className="static-page__avatar" aria-hidden>
                  {initials(member.name)}
                </span>
                <h3 className="static-page__card-title">{member.name}</h3>
                <p className="static-page__role">{member.role}</p>
                <p className="static-page__card-text">{member.focus}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="static-page__section" id="faq" aria-labelledby="about-faq">
          <h2 className="static-page__section-title" id="about-faq">
            Frequently asked questions
          </h2>
          <p className="static-page__section-lead">
            Still unsure? The assistant in the corner answers in your language, or you can{' '}
            <Link to="/contact" className="static-page__card-link">
              contact us
            </Link>
            .
          </p>
          <div className="static-page__prose">
            <Accordion key={openFaq ?? 'none'} items={faq(horizonDays)} openId={openFaq} idPrefix="faq" />
          </div>
        </section>

        <section className="static-page__actions" aria-label="Next steps">
          <Button asChild>
            <Link to="/products">Browse produce</Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/contact">Contact us</Link>
          </Button>
        </section>
      </div>
    </div>
  );
}
