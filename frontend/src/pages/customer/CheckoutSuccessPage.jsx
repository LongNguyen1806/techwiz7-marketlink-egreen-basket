import { Link, useLocation } from 'react-router-dom';
import { CircleCheck } from 'lucide-react';
import { StatusBadge } from '../../components/common/StatusBadge';
import { Button } from '../../components/ui/Button';
import { formatDate, formatMoney, formatTime } from '../../utils/formatters';
import '../../styles/customer/CheckoutSuccessPage.css';

/**
 * C-03. The orders come through the navigation state, which a reload loses — the orders themselves are
 * safe on the server, so the page then simply points at C-04 instead of inventing a summary.
 */
export default function CheckoutSuccessPage() {
  const location = useLocation();
  const orders = location.state?.orders ?? [];

  return (
    <section className="checkout-success">
      {orders.length > 0 ? (
        <>
          <span className="checkout-success__icon-wrap">
            <CircleCheck className="checkout-success__icon" strokeWidth={1.75} aria-hidden />
          </span>
          <h1 className="checkout-success__title">
            {`${orders.length} order${orders.length > 1 ? 's' : ''} placed successfully`}
          </h1>
          <p className="checkout-success__note">
            Farmers will confirm your orders. You&apos;ll be notified when each order is accepted and
            when it&apos;s ready for pickup.
          </p>

          <ul className="checkout-success__orders">
            {orders.map((order) => (
              <li key={order.id} className="checkout-success__order">
                <div className="checkout-success__order-head">
                  <Link to={`/customer/orders/${order.id}`} className="checkout-success__order-id">
                    {`#${order.id}`}
                  </Link>
                  <StatusBadge status={order.status} />
                </div>
                <p className="checkout-success__order-stall">{order.farmer.stall_name}</p>
                <p className="checkout-success__order-where">
                  {order.market.name}
                  {order.stall_label ? ` · ${order.stall_label}` : ''}
                </p>
                <p className="checkout-success__order-when">
                  {`${formatDate(order.pickup_date)} · ${formatTime(order.pickup_start_at)}–${formatTime(order.pickup_end_at)}`}
                </p>
                <p className="checkout-success__order-total">{formatMoney(order.total_amount)}</p>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <>
          <h1 className="checkout-success__title">Your orders</h1>
          <p className="checkout-success__note">
            This page only shows a summary right after checkout. Your orders are listed in full under
            my orders.
          </p>
        </>
      )}

      <div className="checkout-success__actions">
        <Button asChild>
          <Link to="/customer/orders">View my orders</Link>
        </Button>
        <Button asChild variant="outline">
          <Link to="/products">Continue shopping</Link>
        </Button>
      </div>
    </section>
  );
}
