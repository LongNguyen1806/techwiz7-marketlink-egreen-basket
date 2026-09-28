import { NavLink } from 'react-router-dom';

import { cn } from '../../lib/cn';
import '../../styles/admin/AccountsTabs.css';

const TABS = [
  { to: '/admin/farmers', label: 'Stalls' },
  { to: '/admin/customers', label: 'Shoppers' },
];

export function AccountsTabs() {
  return (
    <nav className="accounts-tabs" aria-label="Accounts">
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          className={({ isActive }) => cn('accounts-tabs__tab', isActive && 'is-active')}
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}
