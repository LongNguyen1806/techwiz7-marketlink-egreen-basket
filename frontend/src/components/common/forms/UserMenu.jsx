import { Link } from 'react-router-dom';
import { Heart, KeyRound, LayoutDashboard, LogOut, UserRound } from 'lucide-react';

import { Avatar, AvatarFallback } from '@/components/common/avatar/Avatar';
import { Button } from '@/components/common/forms/Button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/common/layout/DropdownMenu';
import { DASHBOARD_PATH } from '@/config/constants';
import { useAuth, useLogout } from '../../../hooks/authentication/useAuth';

import './UserMenu.css';

function initials(displayName, email) {
  const parts = displayName.trim().split(/\s+/);
  if (parts.length >= 2) {
    return `${parts[0].charAt(0)}${parts[parts.length - 1].charAt(0)}`.toUpperCase();
  }
  if (parts[0]) return parts[0].charAt(0).toUpperCase();
  return email.trim().charAt(0).toUpperCase() || '?';
}

function linksForRole(role) {
  if (role === 'CUSTOMER') {
    return [
      { to: '/app/profile', label: 'Your profile', icon: UserRound },
      { to: '/app/favorites', label: 'Saved favorites', icon: Heart },
      { to: DASHBOARD_PATH.CUSTOMER, label: 'Your overview', icon: LayoutDashboard },
      { to: '/app/change-password', label: 'Change password', icon: KeyRound },
    ];
  }
  if (role === 'FARMER') {
    return [
      { to: '/farmer/profile', label: 'Stall profile', icon: UserRound },
      { to: DASHBOARD_PATH.FARMER, label: 'Stall overview', icon: LayoutDashboard },
      { to: '/farmer/settings', label: 'Change password', icon: KeyRound },
    ];
  }
  return [
    { to: DASHBOARD_PATH.ADMIN, label: 'Admin overview', icon: LayoutDashboard },
    { to: '/admin/password', label: 'Change password', icon: KeyRound },
  ];
}

export function UserMenu() {
  const { user } = useAuth();
  const { mutate: logout } = useLogout();

  if (!user) return null;

  const name = user.display_name || user.email;
  const fallback = initials(user.display_name, user.email);
  const links = linksForRole(user.role);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Account"
          className="user-menu__trigger"
        >
          <Avatar className="user-menu__avatar">
            <AvatarFallback className="user-menu__avatar-fallback">
              {fallback}
            </AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="user-menu__content">
        <DropdownMenuLabel className="user-menu__label">
          <p className="user-menu__name">{name}</p>
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
        <DropdownMenuItem className="user-menu__logout" onSelect={() => logout()}>
          <LogOut className="user-menu__logout-icon" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
