import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { ShoppingBasket } from 'lucide-react';
import { ThemeToggle } from '../components/layout/ThemeToggle';
import { Button } from '../components/ui/Button';
import { UserMenu } from '../components/common/layout/UserMenu';
import { MiniCartDrawer } from '../components/common/drawer/MiniCartDrawer';
import { AnnouncementBanner } from '../components/common/announcements/AnnouncementBanner';
import { NotificationBell } from '../components/common/layout/NotificationBell';
import { usePrefetchRoutes } from '../hooks/usePrefetchRoutes';
import { DASHBOARD_PATH } from '../constants';
import { useAuthStore } from '../stores/auth.store';
import { cn } from '../lib/cn';
import '../styles/guest/PublicLayout.css';
const footerLinkClass = 'public-layout__footer-link';
export function PublicLayout() {
    const location = useLocation();
    const accessToken = useAuthStore((s) => s.accessToken);
    const role = useAuthStore((s) => s.role);
    const prefetch = usePrefetchRoutes();
    const isCustomerApp = location.pathname.startsWith(DASHBOARD_PATH.CUSTOMER);
    const isCustomer = Boolean(accessToken) && role === 'CUSTOMER';
    const appHome = DASHBOARD_PATH[role] ?? '/';
    const navLinkClass = ({ isActive }) => cn('public-layout__nav-link', isActive && 'is-active');
    return (<div className="public-layout">
      <a href="#main-content" className="public-layout__skip-link">
        Skip to main content
      </a>

      <header className="public-layout__header">
        <div className="public-layout__header-inner">
          <Link to="/" className="public-layout__logo">
            <span className="public-layout__logo-icon-wrap">
              <ShoppingBasket className="public-layout__logo-icon" strokeWidth={1.75}/>
            </span>
            <span className="public-layout__logo-text">
              Market<span className="public-layout__logo-accent">Link</span>
            </span>
          </Link>

          <nav className="public-layout__nav-desktop" aria-label="Public navigation">
            <NavLink to="/markets" className={navLinkClass} onMouseEnter={prefetch.prefetchMarkets} onFocus={prefetch.prefetchMarkets}>
              Markets
            </NavLink>
            <NavLink to="/products" className={navLinkClass} onMouseEnter={prefetch.prefetchProducts} onFocus={prefetch.prefetchProducts}>
              Produce
            </NavLink>
            <NavLink to="/farmers" className={navLinkClass} onMouseEnter={prefetch.prefetchFarmers} onFocus={prefetch.prefetchFarmers}>
              Stalls
            </NavLink>
          </nav>

          <div className="public-layout__actions">
            <ThemeToggle />
            {isCustomer ? (<>
                <NotificationBell role="CUSTOMER" listPath="/customer/notifications"/>
                <MiniCartDrawer />
                <UserMenu />
              </>) : accessToken ? (<UserMenu />) : (<>
                <Button asChild variant="ghost" size="sm" className="public-layout__login-btn">
                  <Link to="/login">Sign in</Link>
                </Button>
                <Button asChild size="sm">
                  <Link to="/register">Sign up</Link>
                </Button>
              </>)}
          </div>
        </div>

        <nav className="public-layout__nav-mobile" aria-label="Public navigation">
          <NavLink to="/markets" className={navLinkClass} onMouseEnter={prefetch.prefetchMarkets} onFocus={prefetch.prefetchMarkets}>
            Markets
          </NavLink>
          <NavLink to="/products" className={navLinkClass} onMouseEnter={prefetch.prefetchProducts} onFocus={prefetch.prefetchProducts}>
            Produce
          </NavLink>
          <NavLink to="/farmers" className={navLinkClass} onMouseEnter={prefetch.prefetchFarmers} onFocus={prefetch.prefetchFarmers}>
            Stalls
          </NavLink>
        </nav>
      </header>

      <main id="main-content" className="public-layout__main" tabIndex={-1}>
        <AnnouncementBanner />
        <Outlet />
      </main>

      {!isCustomerApp ? (<footer className="public-layout__footer">
          <div className="public-layout__footer-inner">
            <div className="public-layout__footer-grid">
              <div className="public-layout__footer-about">
                <Link to="/" className="public-layout__logo">
                  <span className="public-layout__logo-icon-wrap">
                    <ShoppingBasket className="public-layout__logo-icon" strokeWidth={1.75}/>
                  </span>
                  <span className="public-layout__logo-text">
                    Market<span className="public-layout__logo-accent">Link</span>
                  </span>
                </Link>
                <p className="public-layout__footer-desc">
                  Local markets, reserved for you — pre-order from trusted stalls,
                  pick up on your schedule, and pay when you collect.
                </p>
              </div>

              <div>
                <p className="public-layout__footer-heading">Explore</p>
                <ul className="public-layout__footer-links">
                  <li>
                    <Link to="/markets" className={footerLinkClass}>
                      Local markets
                    </Link>
                  </li>
                  <li>
                    <Link to="/products" className={footerLinkClass}>
                      Market produce
                    </Link>
                  </li>
                  <li>
                    <Link to="/farmers" className={footerLinkClass}>
                      Farmer stalls
                    </Link>
                  </li>
                </ul>
              </div>

              <div>
                <p className="public-layout__footer-heading">Account</p>
                <ul className="public-layout__footer-links">
                  {accessToken ? (<li>
                      <Link to={appHome} className={footerLinkClass}>
                        Go to dashboard
                      </Link>
                    </li>) : (<>
                      <li>
                        <Link to="/login" className={footerLinkClass}>
                          Sign in
                        </Link>
                      </li>
                      <li>
                        <Link to="/register" className={footerLinkClass}>
                          Create customer account
                        </Link>
                      </li>
                      <li>
                        <Link to="/register/farmer" className={footerLinkClass}>
                          Open a stall
                        </Link>
                      </li>
                    </>)}
                </ul>
              </div>
            </div>

            <div className="public-layout__footer-bottom">
              <p>© {new Date().getFullYear()} MarketLink · eGreen Basket</p>
              <p>Farm fresh, just a click away</p>
            </div>
          </div>
        </footer>) : null}
    </div>);
}
