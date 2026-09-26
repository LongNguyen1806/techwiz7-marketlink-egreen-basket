import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { Button } from '../../ui/Button';
import './OrderActions.css';


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
