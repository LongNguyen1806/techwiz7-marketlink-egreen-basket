import PropTypes from 'prop-types';
import { Clock } from 'lucide-react';
import { Badge } from '../ui/Badge';
import { formatDateTime, formatMoney, formatPickupWindow } from '../../utils/formatters';
import { quantityLabel } from '../../utils/labels';
import '../../styles/farmer/FarmerChangeRequestPanel.css';

export function FarmerChangeRequestPanel({ order }) {
  const change = order.pending_change;

  if (!change) {
    return (
      <section className="farmer-change-request" aria-labelledby="farmer-change-request-title">
        <h2 className="farmer-change-request__title" id="farmer-change-request-title">
          Change request
        </h2>
        <p className="farmer-change-request__muted">
          The shopper asked to change this order, but the details couldn&apos;t be read. Keep the original order and
          ask them to send it again.
        </p>
      </section>
    );
  }

  const requested = change.items ?? [];
  const requestedIds = new Set(requested.map((item) => item.product_id));
  const removed = change.items ? order.items.filter((item) => !requestedIds.has(item.product_id)) : [];

  return (
    <section className="farmer-change-request" aria-labelledby="farmer-change-request-title">
      <div className="farmer-change-request__head">
        <h2 className="farmer-change-request__title" id="farmer-change-request-title">
          Change request
        </h2>
        <Badge variant="warning">Waiting for you</Badge>
      </div>

      <p className="farmer-change-request__meta">
        <Clock className="farmer-change-request__icon" aria-hidden />
        {`Sent ${formatDateTime(change.requested_at)} · decide before ${formatDateTime(change.expires_at)}, or it lapses`}
      </p>

      {change.items ? (
        <ul className="farmer-change-request__items">
          {requested.map((item) => {
            const extra = item.quantity - item.current_quantity;
            const short = extra > item.stock_available;
            return (
              <li key={item.product_id} className="farmer-change-request__item">
                <div>
                  <p className="farmer-change-request__item-name">
                    {item.product_name}
                    {item.current_quantity === 0 ? (
                      <Badge variant="accent" className="farmer-change-request__tag">
                        New item
                      </Badge>
                    ) : null}
                  </p>
                  {short ? (
                    <p className="farmer-change-request__warn">
                      Needs {quantityLabel(extra, item.unit)} more, only {quantityLabel(item.stock_available, item.unit)} left in stock
                    </p>
                  ) : null}
                </div>
                <span
                  className={
                    extra === 0
                      ? 'farmer-change-request__qty farmer-change-request__qty--same'
                      : 'farmer-change-request__qty'
                  }
                >
                  {`${item.current_quantity} → ${quantityLabel(item.quantity, item.unit)}`}
                </span>
              </li>
            );
          })}
          {removed.map((item) => (
            <li key={item.product_id} className="farmer-change-request__item">
              <p className="farmer-change-request__item-name farmer-change-request__item-name--removed">
                {item.product_name}
              </p>
              <span className="farmer-change-request__qty">
                {`${quantityLabel(item.quantity, item.unit)} → Removed`}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="farmer-change-request__muted">Items unchanged.</p>
      )}

      {change.pickup_start_at ? (
        <p className="farmer-change-request__row">
          <span className="farmer-change-request__label">Pickup</span>
          <span>
            <s className="farmer-change-request__old">{formatPickupWindow(order.pickup_start_at, order.pickup_end_at)}</s>{' '}
            {formatPickupWindow(change.pickup_start_at, change.pickup_end_at)}
          </span>
        </p>
      ) : null}

      {change.note !== null && change.note !== undefined ? (
        <p className="farmer-change-request__row">
          <span className="farmer-change-request__label">Note</span>
          <span>{change.note || 'Note removed'}</span>
        </p>
      ) : null}

      <p className="farmer-change-request__row">
        <span className="farmer-change-request__label">Total</span>
        <span className="farmer-change-request__total">
          <s className="farmer-change-request__old">{formatMoney(order.total_amount)}</s>{' '}
          {formatMoney(change.estimated_total)}
        </span>
      </p>
    </section>
  );
}

FarmerChangeRequestPanel.propTypes = {
  order: PropTypes.shape({
    pending_change: PropTypes.object,
    items: PropTypes.array.isRequired,
    total_amount: PropTypes.string,
    pickup_start_at: PropTypes.string,
    pickup_end_at: PropTypes.string,
  }).isRequired,
};
