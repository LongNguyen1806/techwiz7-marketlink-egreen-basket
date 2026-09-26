import { Link } from 'react-router-dom';
import { Heart, KeyRound, LayoutDashboard, LogOut, UserRound } from 'lucide-react';
import { Avatar, AvatarFallback } from '../../ui/Avatar';
import { Button } from '../../ui/Button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../../ui/DropdownMenu';
import { ROLES } from '../../../constants/roles';
import { ROUTES } from '../../../constants/routes';
import { useAuth, useLogout } from '../../../hooks/authentication/useAuth';
import '../../../styles/common/UserMenu.css';

const LINKS_BY_ROLE = {
  [ROLES.CUSTOMER]: [
    { to: ROUTES.CUSTOMER.PROFILE, label: 'Your profile', icon: UserRound },
    { to: ROUTES.CUSTOMER.FAVORITES, label: 'Saved favorites', icon: Heart },
    { to: ROUTES.CUSTOMER.ORDERS, label: 'Your orders', icon: LayoutDashboard },
    { to: ROUTES.CUSTOMER.CHANGE_PASSWORD, label: 'Change password', icon: KeyRound },
  ],
  [ROLES.FARMER]: [
    { to: ROUTES.FARMER.PROFILE, label: 'Stall profile', icon: UserRound },
    { to: ROUTES.FARMER.HOME, label: 'Stall overview', icon: LayoutDashboard },
    { to: ROUTES.FARMER.CHANGE_PASSWORD, label: 'Change password', icon: KeyRound },
  ],
};

function initials(displayName, email) {
  const parts = (displayName ?? '').trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
  if (parts.length === 1) return parts[0][0].toUpperCase();
  return (email ?? '?').trim().charAt(0).toUpperCase() || '?';
}

export function UserMenu() {
  const { user } = useAuth();
  const logout = useLogout();
  if (!user) return null;

  const links = LINKS_BY_ROLE[user.role] ?? [];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Account menu" className="user-menu__trigger">
          <Avatar className="user-menu__avatar">
            <AvatarFallback className="user-menu__avatar-fallback">
              {initials(user.display_name, user.email)}
            </AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="user-menu__content">
        <DropdownMenuLabel className="user-menu__label">
          <p className="user-menu__name">{user.display_name || user.email}</p>
          <p className="user-menu__email">{user.email}</p>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {links.map(({ to, label, icon: Icon }) => (
          <DropdownMenuItem key={to} asChild>
            <Link to={to} className="user-menu__nav-link">
              <Icon className="user-menu__nav-icon" />
              {label}
            </Link>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="user-menu__logout"
          disabled={logout.isPending}
          onSelect={() => logout.mutate()}
        >
          <LogOut className="user-menu__logout-icon" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
