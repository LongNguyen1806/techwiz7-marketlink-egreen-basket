import PropTypes from 'prop-types';
import { Clock } from 'lucide-react';
import { Badge } from '../../ui/Badge';
import { formatDate, formatDateTime, formatMoney, formatTime } from '../../../utils/formatters';
import './ChangeRequestPanel.css';


export function ChangeRequestPanel({ change }) {
  return (
    <section className="change-request" aria-labelledby="change-request-title">
      <div className="change-request__head">
        <h2 className="change-request__title" id="change-request-title">Change request</h2>
        <Badge variant="warning">Waiting for the farmer</Badge>
      </div>

      <p className="change-request__meta">
        <Clock className="change-request__icon" aria-hidden />
        {`Sent ${formatDateTime(change.requested_at)} · the farmer has until ${formatDateTime(change.expires_at)}`}
      </p>

      {change.items ? (
        <ul className="change-request__items">
          {change.items.map((item) => (
            <li className="change-request__item" key={item.product_id}>
              <span className="change-request__item-name">{item.product_name}</span>
              <span className="change-request__item-change">
                {`${item.current_quantity} → ${item.quantity} ${item.unit}`}
              </span>
            </li>
          ))}
        </ul>
      ) : null}

      {change.pickup_start_at ? (
        <p className="change-request__row">
          <span className="change-request__label">New pickup</span>
          <span>
            {`${formatDate(change.pickup_date)} · ${formatTime(change.pickup_start_at)}–${formatTime(change.pickup_end_at)}`}
          </span>
        </p>
      ) : null}

      {change.note ? (
        <p className="change-request__row">
          <span className="change-request__label">Note</span>
          <span>{change.note}</span>
        </p>
      ) : null}

      <p className="change-request__row">
        <span className="change-request__label">Estimated total</span>
        <span className="change-request__total">{formatMoney(change.estimated_total)}</span>
      </p>
    </section>
  );
}

ChangeRequestPanel.propTypes = {
  change: PropTypes.object.isRequired,
};
