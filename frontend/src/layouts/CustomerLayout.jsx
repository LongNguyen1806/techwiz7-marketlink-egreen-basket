import { NavLink, Outlet } from 'react-router-dom';
import { Home, Package, ShoppingCart, UserRound, Store } from 'lucide-react';
import { AnnouncementBanner } from '../components/common/announcements/AnnouncementBanner';
import { useAuth } from '../hooks/authentication/useAuth';
import { cartCount, useCartStore } from '../stores/cart.store';
import { cn } from '../lib/cn';
import '../styles/customer/CustomerLayout.css';

const tabs = [
    { to: '/customer', label: 'Home', icon: Home, end: true },
    { to: '/markets', label: 'Markets', icon: Store, end: false },
    { to: '/customer/cart', label: 'Cart', icon: ShoppingCart, end: false },
    { to: '/customer/orders', label: 'Orders', icon: Package, end: false },
    { to: '/customer/profile', label: 'Me', icon: UserRound, end: false },
];
export function CustomerLayout() {
    const { user } = useAuth();
    const lines = useCartStore((s) => s.lines);
    const count = cartCount(lines);
    return (<div className="customer-layout">
      <div className="customer-layout__content">
        <AnnouncementBanner />
        <p className="customer-layout__greeting">
          Welcome back,{' '}
          <span className="customer-layout__greeting-name">
            {user?.display_name || user?.email}
          </span>
        </p>
        <Outlet />
      </div>

      <nav className="glass customer-layout__tab-bar" aria-label="Main navigation">
        <ul className="customer-layout__tab-list">
          {tabs.map((tab) => (<li key={tab.to}>
              <NavLink to={tab.to} end={tab.end} className={({ isActive }) => cn('customer-layout__tab-link', isActive && 'is-active')}>
                <tab.icon className="customer-layout__tab-icon"/>
                {tab.label}
                {tab.to === '/customer/cart' && count > 0 ? (<span className="customer-layout__cart-badge">{count}</span>) : null}
              </NavLink>
            </li>))}
        </ul>
      </nav>
    </div>);
}
