import { Link } from 'react-router-dom';
import PropTypes from 'prop-types';
import { Bell, Package, ShoppingBasket, Star } from 'lucide-react';
import { Countdown } from '../../components/common/Countdown';
import { DirectionsButton } from '../../components/common/maps/DirectionsButton';
import { FarmerCard } from '../../components/common/cards/FarmerCard';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { StatusBadge } from '../../components/common/StatusBadge';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { useCustomerDashboard } from '../../hooks/queries/customer/useCustomerDashboard';
import { useReorder } from '../../hooks/queries/customer/useReorder';
import { formatDate, formatRelative, formatTime } from '../../utils/formatters';
import { cn } from '../../lib/cn';
import '../../styles/customer/CustomerDashboard.css';

/**
 * The four numbers of C-00. CU-05 filters by `tab` and `status` only, so "To review" points at the
 * completed orders — the list where the Review button lives — rather than a filter that has no
 * server side.
 */
const STATS = [
  { key: 'open', label: 'Open orders', to: '/customer/orders?tab=open', icon: Package },
  { key: 'ready_for_pickup', label: 'Ready for pickup', to: '/customer/orders?status=READY_FOR_PICKUP', icon: ShoppingBasket },
  { key: 'completed', label: 'Completed', to: '/customer/orders?status=COMPLETED', icon: Package },
  { key: 'pending_review', label: 'To review', to: '/customer/orders?status=COMPLETED', icon: Star },
];

function PickupCard({ order }) {
  return (
    <article className="customer-dashboard__pickup">
      <div className="customer-dashboard__pickup-head">
        <Link to={`/customer/orders/${order.id}`} className="customer-dashboard__pickup-stall">
          {order.farmer.stall_name}
        </Link>
        <StatusBadge status={order.status} />
      </div>

      <p className="customer-dashboard__pickup-where">
        {order.market.name}
        {order.stall_label ? <span className="customer-dashboard__pickup-label"> · {order.stall_label}</span> : null}
      </p>

      <p className="customer-dashboard__pickup-when">
        {formatDate(order.pickup_date)} · {formatTime(order.pickup_start_at)}–{formatTime(order.pickup_end_at)}
      </p>

      <div className="customer-dashboard__pickup-foot">
        {/* D-007: the screen shows the moment orders stop being changeable, never the hour count. */}
        <Countdown targetIso={order.cutoff_at} label="Cut-off" />
        <DirectionsButton latitude={order.market.latitude} longitude={order.market.longitude} />
      </div>
    </article>
  );
}

PickupCard.propTypes = { order: PropTypes.object.isRequired };

/** C-00 (CU-01, FR-03 / FR-32). */
export default function CustomerDashboard() {
  const { data, isLoading } = useCustomerDashboard();
  const reorder = useReorder();

  if (isLoading || !data) return <PageSkeleton />;

  const {
    counts, upcoming, favorite_farmers: farmers, favorite_markets: markets,
    recent_notifications: notifications, last_order_id: lastOrderId,
  } = data;
  const hasNothing = upcoming.length === 0 && counts.open === 0 && counts.completed === 0;

  return (
    <section className="customer-dashboard">
      <PageHeader title="My MarketLink" description="Your reservations, the stalls you follow, and what needs doing." />

      <div className="customer-dashboard__stats">
        {STATS.map(({ key, label, to, icon: Icon }) => (
          <Link
            key={key}
            to={to}
            className={cn(
              'customer-dashboard__stat',
              key === 'ready_for_pickup' && counts[key] > 0 && 'is-highlighted',
            )}
          >
            <Icon className="customer-dashboard__stat-icon" aria-hidden />
            <span className="customer-dashboard__stat-value">{counts[key]}</span>
            <span className="customer-dashboard__stat-label">{label}</span>
          </Link>
        ))}
      </div>

      {hasNothing ? (
        <div className="customer-dashboard__empty">
          <p className="customer-dashboard__empty-title">You have no orders yet</p>
          <p className="customer-dashboard__empty-text">
            Reserve produce from a stall and pay when you collect it at the market.
          </p>
          <Button asChild>
            <Link to="/products">Browse products</Link>
          </Button>
        </div>
      ) : (
        <section className="customer-dashboard__block" aria-labelledby="next-pickups">
          <h2 className="customer-dashboard__block-title" id="next-pickups">Next pickups</h2>
          {upcoming.length === 0 ? (
            <p className="customer-dashboard__note">Nothing to collect in the next few days.</p>
          ) : (
            <div className="customer-dashboard__pickups">
              {upcoming.map((order) => <PickupCard key={order.id} order={order} />)}
            </div>
          )}
        </section>
      )}

      {lastOrderId ? (
        <div className="customer-dashboard__shortcut">
          {/* CU-09 is read-only: it fills the cart at today's prices and names anything it skipped. */}
          <Button
            type="button"
            variant="outline"
            loading={reorder.isPending}
            onClick={() => reorder.mutate(lastOrderId)}
          >
            Reorder last order
          </Button>
        </div>
      ) : null}

      {farmers.length > 0 ? (
        <section className="customer-dashboard__block" aria-labelledby="favorite-farmers">
          <h2 className="customer-dashboard__block-title" id="favorite-farmers">Stalls you follow</h2>
          <div className="customer-dashboard__farmers">
            {farmers.map((farmer) => <FarmerCard key={farmer.id} farmer={farmer} />)}
          </div>
        </section>
      ) : null}

      {markets.length > 0 ? (
        <section className="customer-dashboard__block" aria-labelledby="saved-markets">
          <h2 className="customer-dashboard__block-title" id="saved-markets">Saved markets</h2>
          <ul className="customer-dashboard__markets">
            {markets.map((market) => (
              <li key={market.id} className="customer-dashboard__market">
                <Link to={`/markets/${market.id}`} className="customer-dashboard__market-name">{market.name}</Link>
                <Badge variant="outline">{`${market.open_time}–${market.close_time}`}</Badge>
                <DirectionsButton latitude={market.latitude} longitude={market.longitude} />
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="customer-dashboard__block" aria-labelledby="latest-notifications">
        <div className="customer-dashboard__block-head">
          <h2 className="customer-dashboard__block-title" id="latest-notifications">Latest updates</h2>
          <Link to="/customer/notifications" className="customer-dashboard__block-link">All notifications</Link>
        </div>
        {notifications.length === 0 ? (
          <p className="customer-dashboard__note">No updates yet.</p>
        ) : (
          <ul className="customer-dashboard__notifications">
            {notifications.map((note) => (
              <li key={note.id} className={cn('customer-dashboard__notification', !note.is_read && 'is-unread')}>
                <Bell className="customer-dashboard__notification-icon" aria-hidden />
                <div>
                  <Link to={note.target_url ?? '/customer/notifications'} className="customer-dashboard__notification-title">
                    {note.title}
                  </Link>
                  <p className="customer-dashboard__notification-text">{note.message}</p>
                </div>
                <time className="customer-dashboard__notification-time" dateTime={note.created_at}>
                  {formatRelative(note.created_at)}
                </time>
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}
