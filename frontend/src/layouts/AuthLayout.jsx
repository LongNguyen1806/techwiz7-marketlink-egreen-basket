import { Link, Outlet } from 'react-router-dom';
import { ArrowLeft, ShoppingBasket } from 'lucide-react';
import { ThemeToggle } from '../components/layout/ThemeToggle';
import { ROUTES } from '../constants/routes';
import '../styles/auth/AuthLayout.css';

const AUTH_VIDEO = '/banner.mp4';

export function AuthLayout() {
  return (
    <div className="auth-layout">
      <a href="#main-content" className="auth-layout__skip-link">
        Skip to main content
      </a>

      <aside className="auth-layout__aside">
        <video className="auth-layout__video" autoPlay muted loop playsInline preload="metadata" aria-hidden>
          <source src={AUTH_VIDEO} type="video/mp4" />
        </video>
        <div className="auth-layout__aside-overlay" />
        <div className="auth-layout__aside-overlay auth-layout__aside-overlay--bottom" />

        <div className="auth-layout__aside-inner">
          <Link to={ROUTES.HOME} className="auth-layout__brand">
            <span className="auth-layout__brand-icon-wrap">
              <ShoppingBasket className="auth-layout__brand-icon" strokeWidth={1.75} />
            </span>
            <span className="auth-layout__brand-name">MarketLink</span>
          </Link>

          <div className="auth-layout__hero-copy">
            <p className="auth-layout__hero-title">MarketLink</p>
            <h1 className="auth-layout__hero-heading">Local markets, reserved for you</h1>
            <p className="auth-layout__hero-desc">
              Pre-order from trusted stalls, pick up on your schedule, and pay when you collect — no delivery fees.
            </p>
          </div>

          <p className="auth-layout__aside-tagline">Farm fresh, just a click away</p>
        </div>
      </aside>

      <div className="auth-layout__panel">
        <div className="auth-layout__panel-glow" />

        <header className="auth-layout__header">
          <Link to={ROUTES.HOME} className="auth-layout__mobile-brand">
            <span className="auth-layout__mobile-brand-icon">
              <ShoppingBasket className="auth-layout__brand-icon" strokeWidth={1.75} />
            </span>
            Market<span className="auth-layout__mobile-brand-accent">Link</span>
          </Link>

          <Link to={ROUTES.HOME} className="auth-layout__home-link">
            <ArrowLeft className="auth-layout__home-link-icon" />
            Back to home
          </Link>

          <ThemeToggle />
        </header>

        <div id="main-content" className="auth-layout__main" tabIndex={-1}>
          <div className="auth-layout__main-inner">
            <Outlet />
          </div>
        </div>
      </div>
    </div>
  );
}
