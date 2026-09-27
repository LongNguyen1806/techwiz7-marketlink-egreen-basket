import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';

import { ROUTES } from '../../constants/routes';
import { useCategories, usePublicFarmers, usePublicMarkets } from '../../hooks/queries/guest/usePublicCatalog';
import '../../styles/guest/StaticPages.css';

// Enough for a sitemap page; each directory page lists the rest.
const LIST_ALL = { page_size: 50 };

const SIGN_IN = 'sign in';

// Fixed sections. `note` marks pages that need an account.
const SECTIONS = [
  {
    title: 'Shop',
    lead: 'Find produce, markets and the stalls that sell there.',
    links: [
      { to: '/', label: 'Home' },
      { to: '/products', label: 'Produce' },
      { to: '/markets', label: 'Markets' },
      { to: '/farmers', label: 'Farmer stalls' },
    ],
  },
  {
    title: 'Your account',
    lead: 'Reserve, track and manage your orders.',
    links: [
      { to: ROUTES.LOGIN, label: 'Sign in' },
      { to: ROUTES.REGISTER_CUSTOMER, label: 'Create an account' },
      { to: '/customer/cart', label: 'Cart', note: SIGN_IN },
      { to: ROUTES.CUSTOMER.ORDERS, label: 'My orders', note: SIGN_IN },
      { to: ROUTES.CUSTOMER.FAVORITES, label: 'Favourites', note: SIGN_IN },
      { to: ROUTES.CUSTOMER.NOTIFICATIONS, label: 'Notifications', note: SIGN_IN },
      { to: ROUTES.CUSTOMER.PROFILE, label: 'Profile', note: SIGN_IN },
    ],
  },
  {
    title: 'Sell on MarketLink',
    lead: 'Everything a stall needs, from sign-up to market day.',
    links: [
      { to: ROUTES.REGISTER_FARMER, label: 'Become a seller' },
      { to: ROUTES.FARMER.HOME, label: 'Stall dashboard', note: 'seller account' },
      { to: ROUTES.FARMER.ORDERS, label: 'Orders & picking list', note: 'seller account' },
      { to: ROUTES.FARMER.PRODUCTS, label: 'Your produce', note: 'seller account' },
      { to: ROUTES.FARMER.MARKETS, label: 'Markets, pickup slots & time off', note: 'seller account' },
      { to: ROUTES.FARMER.STOCK_TEMPLATE, label: 'Weekly stock template', note: 'seller account' },
    ],
  },
  {
    title: 'Help & company',
    lead: 'About us, answers and how we handle your information.',
    links: [
      { to: '/about', label: 'About us' },
      { to: '/about#faq', label: 'Frequently asked questions' },
      { to: '/contact', label: 'Contact' },
      { to: '/privacy', label: 'Privacy Policy' },
      { to: '/sitemap', label: 'Sitemap' },
    ],
  },
];

function Group({ title, lead, links, loading = false }) {
  return (
    <section className="static-page__sitemap-group" aria-label={title}>
      <h2 className="static-page__section-title">{title}</h2>
      {lead ? <p className="static-page__section-lead">{lead}</p> : null}
      {loading ? (
        <p className="static-page__section-lead">Loading…</p>
      ) : (
        <ul className="static-page__sitemap-links">
          {links.map((link) => (
            <li key={`${link.to}-${link.label}`}>
              <Link to={link.to} className="static-page__sitemap-link">
                {link.label}
              </Link>
              {link.note ? <span className="static-page__sitemap-note">({link.note})</span> : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

Group.propTypes = {
  title: PropTypes.string.isRequired,
  lead: PropTypes.string,
  links: PropTypes.array.isRequired,
  loading: PropTypes.bool,
};

/** HTML sitemap: every public page, plus the live markets, produce categories and stalls. */
export default function SitemapPage() {
  const marketsQuery = usePublicMarkets(LIST_ALL);
  const categoriesQuery = useCategories();
  const farmersQuery = usePublicFarmers(LIST_ALL);

  const [shop, ...rest] = SECTIONS;

  return (
    <div className="static-page">
      <section className="static-page__hero">
        <div className="static-page__hero-inner">
          <div className="static-page__hero-copy">
            <p className="static-page__eyebrow">Sitemap</p>
            <h1 className="static-page__title">MarketLink sitemap</h1>
            <p className="static-page__lead">Every page on MarketLink in one place.</p>
          </div>
        </div>
      </section>

      <div className="static-page__body">
        <div>
          <Group {...shop} />
          <Group
            title="Produce by category"
            lead="Browse what stalls have on sale, one kind at a time."
            loading={categoriesQuery.isPending}
            links={(categoriesQuery.data ?? []).map((category) => ({
              to: `/products?category=${category.id}`,
              label: category.name,
            }))}
          />
          <Group
            title="Markets"
            lead="Opening days, hours and the stalls at each market."
            loading={marketsQuery.isPending}
            links={(marketsQuery.data?.results ?? []).map((market) => ({ to: `/markets/${market.id}`, label: market.name }))}
          />
          <Group
            title="Farmer stalls"
            lead="What each stall sells, where and when you can pick up."
            loading={farmersQuery.isPending}
            links={(farmersQuery.data?.results ?? []).map((farmer) => ({ to: `/farmers/${farmer.id}`, label: farmer.stall_name }))}
          />
          {rest.map((section) => (
            <Group key={section.title} {...section} />
          ))}
        </div>
      </div>
    </div>
  );
}
