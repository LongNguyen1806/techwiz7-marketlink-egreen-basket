import { Link } from 'react-router-dom';
import { ArrowRight, ClipboardCheck, MapPin, Repeat, ShoppingBasket, Store, Tractor, Users } from 'lucide-react';

import { Accordion } from '../../components/common/Accordion';
import { StatusBadge } from '../../components/common/StatusBadge';
import { Button } from '../../components/ui/Button';
import {
  ABOUT_CHALLENGES,
  ABOUT_REGIONS,
  DEFAULT_BOOKING_HORIZON_DAYS,
  TEAM,
  faq,
  howItWorks,
} from '../../constants/siteContent';
import { useScrollToHash } from '../../hooks/common/useScrollToHash';
import { usePublicConfig } from '../../hooks/queries/guest/usePublicCatalog';
import '../../styles/guest/AboutPage.css';

const CHALLENGE_ICONS = [Users, Tractor];

export default function AboutPage() {
  const configQuery = usePublicConfig();
  const horizonDays = configQuery.data?.booking_horizon_days ?? DEFAULT_BOOKING_HORIZON_DAYS;
  const steps = howItWorks(horizonDays);

  const hash = useScrollToHash();
  const openFaq = hash.startsWith('faq-') ? hash.slice(4) : null;

  return (
    <div className="about-page">
      <section className="about-page__hero">
        <div className="about-page__hero-inner">
          <div className="about-page__hero-copy">
            <p className="about-page__eyebrow">About MarketLink</p>
            <h1 className="about-page__title">Farm Fresh Just a Click Away</h1>
            <p className="about-page__subtitle">
              Pre-order fresh, traceable produce online and pick it up at your local farmers&apos; market.
            </p>
          </div>
        </div>
      </section>

      <section className="about-page__section about-page__why" aria-labelledby="about-story">
        <div className="about-page__why-intro">
          <h2 className="about-page__section-title" id="about-story">
            Why we started MarketLink
          </h2>
          <p className="about-page__section-desc">
            Every market day, farmers and cooperatives bring clean, traceable produce to markets across Ho Chi Minh
            City. But finding out who is selling what, and whether it will still be there when you arrive, has never
            been easy.
          </p>
          <p className="about-page__why-label">Where our produce comes from</p>
          <ul className="about-page__chips">
            {ABOUT_REGIONS.map((region) => (
              <li key={region} className="about-page__chip">
                {region}
              </li>
            ))}
          </ul>
        </div>
        <ol className="about-page__problems">
          {ABOUT_CHALLENGES.map((challenge, index) => {
            const Icon = CHALLENGE_ICONS[index];
            return (
              <li key={challenge.title} className="about-page__problem">
                <span className="about-page__problem-icon">
                  <Icon className="about-page__icon-md" strokeWidth={1.75} aria-hidden />
                </span>
                <div className="about-page__problem-body">
                  <p className="about-page__problem-tag">{challenge.tag}</p>
                  <h3 className="about-page__problem-title">{challenge.title}</h3>
                  <p className="about-page__problem-desc">{challenge.text}</p>
                </div>
              </li>
            );
          })}
        </ol>
      </section>

      <section className="about-page__section" aria-labelledby="about-features">
        <div className="about-page__section-head">
          <h2 className="about-page__section-title" id="about-features">
            Shopping made simple
          </h2>
          <p className="about-page__section-desc">
            Order online, collect at the market — fresh from the farm, without the early rush.
          </p>
        </div>
        <div className="about-page__bento">
          <article className="about-page__tile about-page__tile--map">
            <div className="about-page__map-art" aria-hidden>
              <MapPin className="about-page__map-pin about-page__map-pin--one" />
              <MapPin className="about-page__map-pin about-page__map-pin--two" />
              <MapPin className="about-page__map-pin about-page__map-pin--three" />
            </div>
            <h3 className="about-page__tile-title">
              <MapPin className="about-page__icon-sm" aria-hidden />
              Markets near you
            </h3>
            <p className="about-page__tile-desc">
              Browse markets on an interactive map and pick the one closest to you.
            </p>
          </article>

          <article className="about-page__tile about-page__tile--stock">
            <div className="about-page__tile-copy">
              <h3 className="about-page__tile-title">
                <Repeat className="about-page__icon-sm" aria-hidden />
                Restocked every week
              </h3>
              <p className="about-page__tile-desc">
                Farmers refresh their stalls for each market week, so what you see online is what is waiting for you.
              </p>
            </div>
            <div className="about-page__stock-art" aria-hidden>
              <span className="about-page__stock-chip">New market week</span>
              <Repeat className="about-page__icon-md" />
              <span className="about-page__stock-chip about-page__stock-chip--strong">Fresh stock</span>
            </div>
          </article>

          <article className="about-page__tile about-page__tile--orders">
            <h3 className="about-page__tile-title">
              <ClipboardCheck className="about-page__icon-sm" aria-hidden />
              Confirmed by the farmer
            </h3>
            <p className="about-page__tile-desc">
              Your farmer accepts the order, then lets you know when it is packed and ready to collect.
            </p>
            <div className="about-page__flow" aria-hidden>
              <StatusBadge status="PLACED" />
              <ArrowRight className="about-page__flow-arrow" />
              <StatusBadge status="ACCEPTED" />
              <ArrowRight className="about-page__flow-arrow" />
              <StatusBadge status="READY_FOR_PICKUP" />
            </div>
          </article>

          <article className="about-page__tile about-page__tile--basket">
            <div className="about-page__basket-art" aria-hidden>
              <span className="about-page__stall">
                <Store className="about-page__icon-sm" />
              </span>
              <span className="about-page__stall">
                <Store className="about-page__icon-sm" />
              </span>
              <span className="about-page__stall">
                <Store className="about-page__icon-sm" />
              </span>
              <ArrowRight className="about-page__flow-arrow" />
              <span className="about-page__basket-dot">
                <ShoppingBasket className="about-page__icon-md" />
              </span>
            </div>
            <h3 className="about-page__tile-title">One basket, many farmers</h3>
            <p className="about-page__tile-desc">
              Shop from several stalls and check out once, with your own pickup time at each stall.
            </p>
          </article>
        </div>
      </section>

      <section className="about-page__how" aria-labelledby="about-how">
        <div className="about-page__how-inner">
          <div className="about-page__section-head">
            <h2 className="about-page__section-title" id="about-how">
              How it works
            </h2>
            <p className="about-page__section-desc">From browse to bag in {steps.length} simple steps.</p>
          </div>
          <ol className="about-page__steps">
            {steps.map((step, index) => (
              <li key={step.title} className="about-page__step">
                <div className="about-page__step-head">
                  <span className="about-page__step-num">{String(index + 1).padStart(2, '0')}</span>
                  <h3 className="about-page__step-title">{step.title}</h3>
                </div>
                <p className="about-page__step-desc">{step.text}</p>
                {index < steps.length - 1 ? (
                  <span className="about-page__step-arrow" aria-hidden>
                    <ArrowRight className="about-page__step-arrow-icon" />
                  </span>
                ) : null}
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="about-page__section" aria-labelledby="about-team">
        <div className="about-page__section-head">
          <h2 className="about-page__section-title" id="about-team">
            The team
          </h2>
          <p className="about-page__section-desc">The people who designed and built MarketLink.</p>
        </div>
        <ul className="about-page__team">
          {TEAM.map((member) => (
            <li key={member.name} className="about-page__member">
              <h3 className="about-page__member-name">{member.name}</h3>
              <p className="about-page__member-role">{member.role}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="about-page__faq" id="faq" aria-labelledby="about-faq">
        <div className="about-page__faq-inner">
          <div className="about-page__section-head">
            <h2 className="about-page__section-title" id="about-faq">
              Frequently asked questions
            </h2>
            <p className="about-page__section-desc">
              Still unsure? The assistant in the corner answers in your language, or you can{' '}
              <Link to="/contact" className="about-page__link">
                contact us
              </Link>
              .
            </p>
          </div>
          <div className="about-page__faq-list">
            <Accordion key={openFaq ?? 'none'} items={faq(horizonDays)} openId={openFaq} idPrefix="faq" />
          </div>
        </div>
      </section>

      <section className="about-page__cta">
        <div className="about-page__cta-inner">
          <div className="about-page__cta-copy">
            <p className="about-page__cta-title">Ready for your next market run?</p>
            <p className="about-page__cta-desc">Find a market nearby or reach out to our team with any question.</p>
          </div>
          <div className="about-page__cta-actions">
            <Button asChild size="lg" variant="accent">
              <Link to="/markets">
                Explore markets
                <ArrowRight className="about-page__icon-sm" aria-hidden />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline" className="about-page__cta-outline">
              <Link to="/contact">Contact us</Link>
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}
