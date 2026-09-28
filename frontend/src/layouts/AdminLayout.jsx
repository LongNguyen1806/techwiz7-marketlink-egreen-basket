import { NavLink, Outlet, Link, useLocation } from 'react-router-dom';
import {
  ClipboardList,
  FolderTree,
  LayoutDashboard,
  Menu,
  ShieldAlert,
  Store,
  Users,
  Megaphone,
  ScrollText,
  SlidersHorizontal,
  BadgeCheck,
  ReceiptText,
} from 'lucide-react';

import { ThemeToggle } from '../components/layout/ThemeToggle';
import { NotificationBell } from '@/components/common/layout/NotificationBell';
import { Button } from '../components/ui/Button';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '../components/ui/Sheet';
import { UserMenu } from '../components/common/layout/UserMenu';
import { useUiStore } from '../stores/ui.store';
import { useAIReviewStats } from '../hooks/queries/admin/useAdminAIReview';
import { cn } from '../lib/cn';

import '../styles/admin/AdminLayout.css';
import { AIChatWidget } from '../components/common/chat/AIChatWidget';

const NAV_GROUPS = [
  {
    title: 'Operations',
    items: [
      { to: '/admin', label: 'Overview', icon: LayoutDashboard, end: true },
      { to: '/admin/approvals', label: 'Approvals', icon: BadgeCheck, badge: 'approvals' },
      { to: '/admin/orders', label: 'Orders', icon: ReceiptText },
    ],
  },
  {
    title: 'People',
    items: [
      { to: '/admin/farmers', label: 'Accounts', icon: Users, also: ['/admin/customers'] },
    ],
  },
  {
    title: 'Catalog',
    items: [
      { to: '/admin/markets', label: 'Markets', icon: Store },
      { to: '/admin/categories', label: 'Categories', icon: FolderTree },
      { to: '/admin/moderation', label: 'Content moderation', icon: ShieldAlert },
    ],
  },
  {
    title: 'System',
    items: [
      { to: '/admin/announcements', label: 'Announcements', icon: Megaphone },
      { to: '/admin/audit-logs', label: 'System log', icon: ScrollText },
    ],
  },
];

function SideNav({ collapsed }                        ) {
  const aiStats = useAIReviewStats(30);
  const { pathname } = useLocation();
  const badges = {
    approvals: (aiStats.data?.open_ai_flags ?? 0) + (aiStats.data?.unchecked_ai_decisions ?? 0),
  };
  return (
    <nav className="admin-layout__nav">
      {NAV_GROUPS.map((group) => (
        <div key={group.title} className="admin-layout__nav-group">
          {collapsed ? (
            <hr className="admin-layout__nav-divider" />
          ) : (
            <p className="admin-layout__nav-title">{group.title}</p>
          )}
      {group.items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            cn(
              'admin-layout__nav-link',
              (isActive || item.also?.some((path) => pathname.startsWith(path))) && 'is-active',
              collapsed && 'admin-layout__nav-link--collapsed',
            )
          }
          title={item.label}
        >
          <item.icon className="admin-layout__nav-icon" />
          {!collapsed ? <span>{item.label}</span> : null}
          {item.badge && badges[item.badge] ? (
            <span className="admin-layout__nav-badge" title={`${badges[item.badge]} waiting for you`}>
              {badges[item.badge]}
            </span>
          ) : null}
        </NavLink>
      ))}
        </div>
      ))}
    </nav>
  );
}

export function AdminLayout() {
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const setCollapsed = useUiStore((s) => s.setSidebarCollapsed);

  return (
    <div className="admin-layout">
      <a href="#main-content" className="admin-layout__skip-link">
        Skip to main content
      </a>
      <aside
        className={cn(
          'admin-layout__sidebar',
          collapsed
            ? 'admin-layout__sidebar--collapsed'
            : 'admin-layout__sidebar--expanded',
        )}
      >
        <div className="admin-layout__sidebar-head">
          {!collapsed ? (
            <Link to="/admin" className="admin-layout__sidebar-brand">
              <ClipboardList className="admin-layout__sidebar-brand-icon" />
              MarketLink Admin
            </Link>
          ) : null}
          <Button
            variant="ghost"
            size="icon"
            aria-label="Collapse sidebar"
            onClick={() => setCollapsed(!collapsed)}
          >
            <Menu className="admin-layout__nav-icon" />
          </Button>
        </div>
        <SideNav collapsed={collapsed} />
      </aside>

      <div className="admin-layout__body">
        <header className="glass admin-layout__header">
          <div className="admin-layout__header-mobile">
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="outline" size="icon" aria-label="Open menu">
                  <Menu className="admin-layout__nav-icon" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="admin-layout__sheet">
                <SheetHeader className="admin-layout__sheet-header">
                  <SheetTitle>Admin menu</SheetTitle>
                </SheetHeader>
                <SideNav collapsed={false} />
              </SheetContent>
            </Sheet>
            <span className="admin-layout__header-title">MarketLink Admin</span>
          </div>
          <div className="admin-layout__header-actions">
            <Button asChild variant="ghost" size="icon" className="admin-layout__header-icon">
              <Link to="/admin/limits" aria-label="Platform limits" title="Platform limits">
                <SlidersHorizontal className="admin-layout__header-icon-svg" aria-hidden="true" />
              </Link>
            </Button>
            <NotificationBell />
            <ThemeToggle />
            <UserMenu />
          </div>
        </header>
        <main id="main-content" className="admin-layout__main" tabIndex={-1}>
          <Outlet />
        </main>
        <AIChatWidget />
      </div>
    </div>
  );
}
