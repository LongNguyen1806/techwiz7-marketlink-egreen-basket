import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { Button } from '../../ui/Button';
import './OrderActions.css';

/**
 * The buttons of §8.1, taken from the server's `allowed_actions` rather than worked out here.
 *
 * The rules behind it — before the cut-off, the current status, whether anything is left to review —
 * live in `customer_allowed_actions`, and a second copy in the browser would drift from the FSM the
 * moment either changes (D-006).
 */
export function OrderActions({ order, onCancel, onReorder, reorderPending = false, size = 'sm' }) {
  const allowed = order.allowed_actions ?? [];
  const base = `/customer/orders/${order.id}`;

  return (
    <div className="order-actions">
      {allowed.includes('MODIFY') ? (
        <Button asChild variant="outline" size={size}>
          <Link to={`${base}/edit`}>Edit order</Link>
        </Button>
      ) : null}

      {allowed.includes('REQUEST_CHANGE') ? (
        <Button asChild variant="outline" size={size}>
          <Link to={`${base}/edit`}>Request a change</Link>
        </Button>
      ) : null}

      {allowed.includes('REVIEW') ? (
        <Button asChild variant="outline" size={size}>
          <Link to={`${base}/review`}>Write a review</Link>
        </Button>
      ) : null}

      {allowed.includes('REORDER') && onReorder ? (
        <Button type="button" variant="outline" size={size} loading={reorderPending} onClick={() => onReorder(order)}>
          Reorder
        </Button>
      ) : null}

      {allowed.includes('CANCEL') && onCancel ? (
        <Button type="button" variant="destructive" size={size} onClick={() => onCancel(order)}>
          Cancel order
        </Button>
      ) : null}
    </div>
  );
}

OrderActions.propTypes = {
  order: PropTypes.object.isRequired,
  onCancel: PropTypes.func,
  onReorder: PropTypes.func,
  reorderPending: PropTypes.bool,
  size: PropTypes.oneOf(['sm', 'default']),
};
