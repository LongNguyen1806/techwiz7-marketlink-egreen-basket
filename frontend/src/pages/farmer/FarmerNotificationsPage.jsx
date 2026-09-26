import { Link } from 'react-router-dom';
import { ApiError } from '../../lib/ApiError';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Button } from '../../components/ui/Button';
import { useNotifications } from '../../features/notifications/hooks/useNotifications';
import { formatRelative } from '../../utils/formatters';
import '../../styles/farmer/FarmerNotificationsPage.css';
export default function FarmerNotificationsPage() {
    const { query, results, unread, markAll, markOne } = useNotifications('FARMER');
    if (query.isLoading)
        return <PageSkeleton />;
    if (query.isError) {
        return (<EmptyState title="Notifications couldn't be loaded" description={ApiError.fromUnknown(query.error).friendlyMessage} actionLabel="Try again" onAction={() => void query.refetch()}/>);
    }
    return (<div className="farmer-notifications-page">
      <PageHeader title="Stall notifications" description={unread > 0
            ? `${unread} unread update${unread === 1 ? '' : 's'}`
            : 'You are all caught up'} actions={<Button size="sm" variant="outline" loading={markAll.isPending} onClick={() => markAll.mutate()}>
            Mark all as read
          </Button>}/>
      {!results.length ? (<EmptyState title="No notifications yet" description="Order alerts and system updates will appear here."/>) : (<ul className="farmer-notifications-page__list">
          {results.map((item) => (<li key={item.id}>
              <button type="button" className={item.is_read
                    ? 'farmer-notifications-page__item'
                    : 'farmer-notifications-page__item farmer-notifications-page__item--unread'} onClick={() => {
                    if (!item.is_read)
                        markOne.mutate(item.id);
                }}>
                <div className="farmer-notifications-page__row">
                  <div>
                    <p className="farmer-notifications-page__title">{item.title}</p>
                    <p className="farmer-notifications-page__message">{item.message}</p>
                    <p className="farmer-notifications-page__time">
                      {formatRelative(item.created_at)}
                    </p>
                  </div>
                  {!item.is_read ? <span className="page-primitive__dot-unread"/> : null}
                </div>
                {item.target_url ? (<Link to={item.target_url} className="farmer-notifications-page__link" onClick={(e) => e.stopPropagation()}>
                    View details â†’
                  </Link>) : null}
              </button>
            </li>))}
        </ul>)}
    </div>);
}

