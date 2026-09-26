import PropTypes from 'prop-types';
import { Bell } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from '../../ui/Button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../../ui/DropdownMenu';
import {
  useLatestNotifications,
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useUnreadNotificationCount,
} from '../../../hooks/queries/common/useNotifications';
import { formatRelative } from '../../../utils/formatters';
import '../../../styles/common/NotificationBell.css';

function BellBody({ query }) {
  if (query.isPending) return <p className="notification-bell__empty">Loading notifications…</p>;
  if (query.isError) return <p className="notification-bell__empty">We couldn&apos;t load your notifications.</p>;
  if (query.data.length === 0) return <p className="notification-bell__empty">No notifications yet</p>;
  return null;
}

BellBody.propTypes = {
  query: PropTypes.object.isRequired,
};

export function NotificationBell({ listPath }) {
  const navigate = useNavigate();
  const unreadQuery = useUnreadNotificationCount();
  const latestQuery = useLatestNotifications();
  const markAll = useMarkAllNotificationsRead();
  const markOne = useMarkNotificationRead();

  const unread = unreadQuery.data ?? 0;
  const items = latestQuery.data ?? [];

  const openItem = (item) => {
    if (!item.is_read) markOne.mutate(item.id);
    if (item.target_url) navigate(item.target_url);
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label={unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'}
          className="notification-bell__trigger"
        >
          <Bell className="notification-bell__icon" />
          {unread > 0 ? <span className="notification-bell__badge">{unread > 9 ? '9+' : unread}</span> : null}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="notification-bell__content">
        <DropdownMenuLabel className="notification-bell__header">
          <span>Notifications</span>
          {unread > 0 ? (
            <button
              type="button"
              className="notification-bell__mark-read"
              disabled={markAll.isPending}
              onClick={() => markAll.mutate()}
            >
              Mark all as read
            </button>
          ) : null}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <BellBody query={latestQuery} />
        {items.map((item) => (
          <DropdownMenuItem key={item.id} className="notification-bell__item" onSelect={() => openItem(item)}>
            <div className="notification-bell__item-head">
              <p className="notification-bell__item-title">{item.title}</p>
              {!item.is_read ? <span className="notification-bell__unread-dot" aria-label="Unread" /> : null}
            </div>
            <p className="notification-bell__item-message">{item.message}</p>
            <p className="notification-bell__item-time">{formatRelative(item.created_at)}</p>
            {item.target_url ? <span className="notification-bell__item-link">View details</span> : null}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link to={listPath} className="notification-bell__view-all">
            View all
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

NotificationBell.propTypes = {
  listPath: PropTypes.string.isRequired,
};
