import PropTypes from 'prop-types';
import { Badge } from '../../ui/Badge';


const LOW_STOCK = 10;


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
