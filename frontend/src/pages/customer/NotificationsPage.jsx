import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Bell } from 'lucide-react';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Button } from '../../components/ui/Button';
import { Tabs, TabsList, TabsTrigger } from '../../components/ui/Tabs';
import { useNotificationFeed } from '../../hooks/queries/common/useNotificationFeed';
import { formatDateTime, formatRelative } from '../../utils/formatters';
import { cn } from '../../lib/cn';
import '../../styles/customer/NotificationsPage.css';


export default function NotificationsPage() {
  const [filter, setFilter] = useState('all');
  const [page, setPage] = useState(1);
  const { query, markOne, markAll } = useNotificationFeed({
    page,
    isRead: filter === 'unread' ? false : undefined,
  });

  const data = query.data;
  const rows = data?.results ?? [];

  function switchFilter(next) {
    setFilter(next);
    setPage(1);
  }

  return (
    <section className="notifications-page">
      <PageHeader
        title="Notifications"
        description="Order confirmations, pickup reminders and restock alerts."
        actions={(
          <Button type="button" variant="outline" loading={markAll.isPending} onClick={() => markAll.mutate()}>
            Mark all as read
          </Button>
        )}
      />

      <Tabs value={filter} onValueChange={switchFilter}>
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="unread">Unread</TabsTrigger>
        </TabsList>
      </Tabs>

      {query.isLoading ? <PageSkeleton /> : null}

      {!query.isLoading && rows.length === 0 ? (
        <div className="notifications-page__empty">
          <Bell className="notifications-page__empty-icon" aria-hidden />
          <p>No notifications yet.</p>
        </div>
      ) : null}

      {rows.length > 0 ? (
        <ul className="notifications-page__list">
          {rows.map((note) => (
            <li className={cn('notifications-page__item', !note.is_read && 'is-unread')} key={note.id}>
              <div className="notifications-page__item-main">
                {note.target_url ? (
                  <Link
                    to={note.target_url}
                    className="notifications-page__item-title"
                    onClick={() => {
                      
                      if (!note.is_read) markOne.mutate(note.id);
                    }}
                  >
                    {note.title}
                  </Link>
                ) : (
                  <p className="notifications-page__item-title">{note.title}</p>
                )}
                <p className="notifications-page__item-message">{note.message}</p>
                <time className="notifications-page__item-time" dateTime={note.created_at} title={formatDateTime(note.created_at)}>
                  {formatRelative(note.created_at)}
                </time>
              </div>

              {!note.is_read ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => markOne.mutate(note.id)}
                >
                  Mark as read
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      {data && data.total_pages > 1 ? (
        <div className="notifications-page__pager">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={data.previous === null}
            onClick={() => setPage(data.previous)}
          >
            Previous
          </Button>
          <p className="notifications-page__pager-text">{`Page ${data.page} of ${data.total_pages}`}</p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={data.next === null}
            onClick={() => setPage(data.next)}
          >
            Next
          </Button>
        </div>
      ) : null}
    </section>
  );
}
