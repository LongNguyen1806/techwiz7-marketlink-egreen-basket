import PropTypes from 'prop-types';
import { Badge } from '../../ui/Badge';

/** Below this many units the catalogue warns instead of reassuring. */
const LOW_STOCK = 10;

/**
 * What a product's `availability` means to a shopper (G-04, G-05, C-08, F-04). `UNAVAILABLE` is the
 * seller's own pause switch; `OUT_OF_STOCK` is a sell-out, which is the only case that can be
 * followed by a restock alert (D-025).
 */
export function StockBadge({ availability, stockQuantity, className }) {
  if (availability === 'UNAVAILABLE') {
    return <Badge variant="secondary" className={className}>Unavailable</Badge>;
  }
  if (availability === 'OUT_OF_STOCK') {
    return <Badge variant="danger" className={className}>Out of stock</Badge>;
  }
  if (stockQuantity <= LOW_STOCK) {
    return <Badge variant="warning" className={className}>{`Low stock · ${stockQuantity} left`}</Badge>;
  }
  return <Badge variant="success" className={className}>{`${stockQuantity} left`}</Badge>;
}

StockBadge.propTypes = {
  availability: PropTypes.oneOf(['IN_STOCK', 'OUT_OF_STOCK', 'UNAVAILABLE']).isRequired,
  stockQuantity: PropTypes.number.isRequired,
  className: PropTypes.string,
};
