import { Outlet } from 'react-router-dom';
import { ShieldCheck } from 'lucide-react';
import { ThemeToggle } from '../components/layout/ThemeToggle';
import '../styles/admin/AdminAuthLayout.css';

/**
 * A-00, the admin sign-in shell (D-027). Deliberately bare: no public header, no sign-up link and
 * no link back to the storefront, so the page never hints that an admin account exists.
 */
export function AdminAuthLayout() {
  return (
    <div className="admin-auth-layout">
      <a href="#main-content" className="admin-auth-layout__skip-link">
        Skip to main content
      </a>

      <header className="admin-auth-layout__header">
        <ThemeToggle />
      </header>

      <main id="main-content" className="admin-auth-layout__main" tabIndex={-1}>
        <div className="admin-auth-layout__card">
          <div className="admin-auth-layout__brand">
            <span className="admin-auth-layout__brand-icon-wrap">
              <ShieldCheck className="admin-auth-layout__brand-icon" strokeWidth={1.75} />
            </span>
            <span className="admin-auth-layout__brand-name">MarketLink Admin</span>
          </div>

          <Outlet />
        </div>

        <p className="admin-auth-layout__note">
          Administrator accounts are issued by IT. This page is for staff only.
        </p>
      </main>
    </div>
  );
}
