import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Button } from '../../components/ui/Button';
import { useUrlFilters } from '../../hooks/common/useUrlFilters';
import {
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotificationList,
  useUnreadNotificationCount,
} from '../../hooks/queries/common/useNotifications';
import { formatRelative } from '../../utils/formatters';
import '../../styles/farmer/FarmerNotificationsPage.css';

export default function FarmerNotificationsPage() {
  const navigate = useNavigate();
  const { filters, setFilters } = useUrlFilters({ show: 'all' });
  const unreadOnly = filters.show === 'unread';
  const listQuery = useNotificationList({ isRead: unreadOnly ? false : undefined });
  const unreadQuery = useUnreadNotificationCount();
  const markAll = useMarkAllNotificationsRead();
  const markOne = useMarkNotificationRead();

  const unread = unreadQuery.data ?? 0;
  const notifications = listQuery.data?.notifications ?? [];

  const openItem = (item) => {
    if (!item.is_read) markOne.mutate(item.id);
    if (item.target_url) navigate(item.target_url);
  };

  let body;
  if (listQuery.isPending) body = <PageSkeleton />;
  else if (listQuery.isError && !listQuery.data) {
    body = (
      <EmptyState title="Notifications couldn't be loaded" actionLabel="Try again" onAction={() => listQuery.refetch()} />
    );
  } else if (notifications.length === 0) {
    body = unreadOnly ? (
      <EmptyState title="No unread notifications" actionLabel="Show all" onAction={() => setFilters({ show: 'all' })} />
    ) : (
      <EmptyState title="No notifications yet" description="Order alerts and system updates will appear here." />
    );
  } else {
    body = (
      <>
        <ul className="farmer-notifications-page__list" aria-busy={listQuery.isFetching}>
          {notifications.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className={
                  item.is_read
                    ? 'farmer-notifications-page__item'
                    : 'farmer-notifications-page__item farmer-notifications-page__item--unread'
                }
                onClick={() => openItem(item)}
              >
                <div className="farmer-notifications-page__row">
                  <div>
                    <p className="farmer-notifications-page__title">{item.title}</p>
                    <p className="farmer-notifications-page__message">{item.message}</p>
                    <p className="farmer-notifications-page__time">{formatRelative(item.created_at)}</p>
                  </div>
                  {!item.is_read ? <span className="page-primitive__dot-unread" aria-label="Unread" /> : null}
                </div>
                {item.target_url ? <span className="farmer-notifications-page__link">View details →</span> : null}
              </button>
            </li>
          ))}
        </ul>
        {listQuery.hasNextPage ? (
          <div className="page-primitive__justify-center-row">
            <Button variant="outline" size="sm" loading={listQuery.isFetchingNextPage} onClick={() => listQuery.fetchNextPage()}>
              Load more
            </Button>
          </div>
        ) : null}
      </>
    );
  }

  return (
    <div className="farmer-notifications-page">
      <PageHeader
        title="Stall notifications"
        description={unread > 0 ? `${unread} unread update${unread === 1 ? '' : 's'}` : 'You are all caught up'}
        actions={
          <Button
            size="sm"
            variant="outline"
            loading={markAll.isPending}
            disabled={unread === 0}
            onClick={() => markAll.mutate()}
          >
            Mark all as read
          </Button>
        }
      />

      <div className="page-primitive__actions-row" role="group" aria-label="Show">
        <Button size="sm" variant={unreadOnly ? 'outline' : 'default'} aria-pressed={!unreadOnly} onClick={() => setFilters({ show: 'all' })}>
          All
        </Button>
        <Button size="sm" variant={unreadOnly ? 'default' : 'outline'} aria-pressed={unreadOnly} onClick={() => setFilters({ show: 'unread' })}>
          Unread
        </Button>
      </div>

      {body}
    </div>
  );
}
