import { useEffect } from 'react';
import PropTypes from 'prop-types';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  BarChart3,
  Boxes,
  CalendarClock,
  Home,
  LayoutDashboard,
  Menu,
  MessageSquare,
  Package,
  Settings,
  Store,
  UserRound,
} from 'lucide-react';
import { FarmerStatusGate } from '../components/farmer/FarmerStatusGate';
import { ThemeToggle } from '../components/layout/ThemeToggle';
import { NotificationBell } from '../components/common/layout/NotificationBell';
import { UserMenu } from '../components/common/layout/UserMenu';
import { Button } from '../components/ui/Button';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '../components/ui/Sheet';
import { FARMER_STATUS } from '../constants/roles';
import { ROUTES } from '../constants/routes';
import { useAuth } from '../hooks/authentication/useAuth';
import { useNotificationSocket } from '../hooks/common/useNotificationSocket';
import { useFarmerProfile } from '../hooks/queries/farmer/useFarmerProfile';
import { cn } from '../lib/cn';
import { useUiStore } from '../stores/ui.store';
import '../styles/farmer/FarmerLayout.css';

const NAV_ITEMS = [
  { to: ROUTES.FARMER.HOME, label: 'Overview', icon: LayoutDashboard, end: true },
  { to: ROUTES.FARMER.ORDERS, label: 'Orders', icon: Package },
  { to: ROUTES.FARMER.PRODUCTS, label: 'Products', icon: Boxes },
  { to: ROUTES.FARMER.STOCK_TEMPLATE, label: 'Stock template', icon: CalendarClock },
  { to: ROUTES.FARMER.MARKETS, label: 'Markets & slots', icon: Store },
  { to: ROUTES.FARMER.REVIEWS, label: 'Reviews', icon: MessageSquare },
  { to: ROUTES.FARMER.STATS, label: 'Stats', icon: BarChart3 },
  { to: ROUTES.FARMER.PROFILE, label: 'Stall profile', icon: UserRound },
  { to: ROUTES.FARMER.CHANGE_PASSWORD, label: 'Change password', icon: Settings },
];

function SideNav({ collapsed }) {
  return (
    <nav className="farmer-layout__nav" aria-label="Stall workspace">
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            cn('farmer-layout__nav-link', isActive && 'is-active', collapsed && 'farmer-layout__nav-link--collapsed')
          }
          title={item.label}
        >
          <item.icon className="farmer-layout__nav-icon" />
          {!collapsed ? <span>{item.label}</span> : null}
        </NavLink>
      ))}
    </nav>
  );
}

SideNav.propTypes = { collapsed: PropTypes.bool.isRequired };

export function FarmerLayout() {
  const { user } = useAuth();
  const profileQuery = useFarmerProfile();
  const { pathname } = useLocation();
  const collapsed = useUiStore((state) => state.sidebarCollapsed);
  const setCollapsed = useUiStore((state) => state.setSidebarCollapsed);
  const mobileNavOpen = useUiStore((state) => state.mobileNavOpen);
  const setMobileNavOpen = useUiStore((state) => state.setMobileNavOpen);

  
  useNotificationSocket();

  
  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname, setMobileNavOpen]);

  return (
    <div className="farmer-layout">
      <a href="#main-content" className="farmer-layout__skip-link">
        Skip to main content
      </a>
      <aside
        className={cn(
          'farmer-layout__sidebar',
          collapsed ? 'farmer-layout__sidebar--collapsed' : 'farmer-layout__sidebar--expanded',
        )}
      >
        <div className="farmer-layout__sidebar-head">
          {!collapsed ? (
            <Link to={ROUTES.FARMER.HOME} className="farmer-layout__sidebar-brand">
              Stall workspace
            </Link>
          ) : null}
          <Button
            variant="ghost"
            size="icon"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-expanded={!collapsed}
            onClick={() => setCollapsed(!collapsed)}
          >
            <Menu className="farmer-layout__nav-icon" />
          </Button>
        </div>
        <SideNav collapsed={collapsed} />
      </aside>

      <div className="farmer-layout__body">
        <header className="glass farmer-layout__header">
          <div className="farmer-layout__header-mobile">
            <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
              <SheetTrigger asChild>
                <Button variant="outline" size="icon" aria-label="Open menu">
                  <Menu className="farmer-layout__nav-icon" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="farmer-layout__sheet">
                <SheetHeader className="farmer-layout__sheet-header">
                  <SheetTitle>Stall menu</SheetTitle>
                </SheetHeader>
                <SideNav collapsed={false} />
              </SheetContent>
            </Sheet>
            <span className="farmer-layout__header-title">Stall workspace</span>
          </div>
          <div className="farmer-layout__header-actions">
            <NotificationBell listPath={ROUTES.FARMER.NOTIFICATIONS} />
            <ThemeToggle />
            <Button asChild variant="ghost" size="icon" aria-label="MarketLink home">
              <Link to={ROUTES.HOME}>
                <Home className="farmer-layout__nav-icon" />
              </Link>
            </Button>
            <UserMenu />
          </div>
        </header>

        <main id="main-content" className="farmer-layout__main" tabIndex={-1}>
          <FarmerStatusGate
            status={user?.farmer_status ?? FARMER_STATUS.PENDING}
            rejectionReason={profileQuery.data?.status_reason ?? null}
          >
            <Outlet />
          </FarmerStatusGate>
        </main>
      </div>
    </div>
  );
}
