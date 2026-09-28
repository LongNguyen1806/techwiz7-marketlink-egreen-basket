import { Bell } from 'lucide-react';
import { Link } from 'react-router-dom';

import { Button } from '@/components/common/forms/Button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/common/layout/DropdownMenu';
import { useNotifications } from '../../../hooks/queries/common/useNotifications';
import { formatRelative } from '@/utils/formatters';

import './NotificationBell.css';

export function NotificationBell({ role, listPath }) {
  const { unread, latest, markAll, markOne } = useNotifications(role);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Notifications"
          className="notification-bell__trigger"
        >
          <Bell className="notification-bell__icon" />
          {unread > 0 ? (
            <span className="notification-bell__badge">{unread > 9 ? '9+' : unread}</span>
          ) : null}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="notification-bell__content">
        <DropdownMenuLabel className="notification-bell__header">
          <span>Notifications</span>
          {unread > 0 ? (
            <button
              type="button"
              className="notification-bell__mark-read"
              onClick={() => markAll.mutate()}
            >
              Mark as read
            </button>
          ) : null}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {latest.length === 0 ? (
          <p className="notification-bell__empty">No notifications yet</p>
        ) : (
          latest.map((item) => (
            <DropdownMenuItem
              key={item.id}
              className="notification-bell__item"
              onSelect={() => {
                if (!item.is_read) markOne.mutate(item.id);
              }}
            >
              <div className="notification-bell__item-head">
                <p className="notification-bell__item-title">{item.title}</p>
                {!item.is_read ? (
                  <span className="notification-bell__unread-dot" />
                ) : null}
              </div>
              <p className="notification-bell__item-message">{item.message}</p>
              <p className="notification-bell__item-time">
                {formatRelative(item.created_at)}
              </p>
              {item.target_url ? (
                <Link
                  to={item.target_url}
                  className="notification-bell__item-link"
                  onClick={(e) => e.stopPropagation()}
                >
                  View details
                </Link>
              ) : null}
            </DropdownMenuItem>
          ))
        )}
        {/* The admin portal has no full notifications page, so it leaves listPath out. */}
        {listPath ? (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link to={listPath} className="notification-bell__view-all">
                View all
              </Link>
            </DropdownMenuItem>
          </>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
