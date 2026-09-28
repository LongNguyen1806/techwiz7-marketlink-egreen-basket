import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { Trash2 } from 'lucide-react';
import { LazyImage } from '../../common/LazyImage';
import { PriceTag } from '../../common/cards/PriceTag';
import { QuantityStepper } from '../../common/QuantityStepper';
import { Badge } from '../../ui/Badge';
import { Button } from '../../ui/Button';
import { MAX_QUANTITY, isOrderable, lineMax, lineMin } from '../../../stores/cart.store';
import { formatMoney } from '../../../utils/formatters';
import { orderWindowLabel, quantityLabel, unitLabel } from '../../../utils/labels';
import { moneyToNumber } from '../../../utils/helpers/domain';
import { cn } from '../../../lib/cn';
import './CartLine.css';


export function CartLine({ line, onQuantityChange, onRemove }) {
  const orderable = isOrderable(line);
  const stock = line.stock_quantity;
  const short = orderable && stock !== undefined && stock < line.quantity;

  return (
    <li className={cn('cart-line', !orderable && 'is-unavailable')} aria-label={line.name}>
      <Link to={`/products/${line.product_id}`} className="cart-line__media" aria-hidden tabIndex={-1}>
        <LazyImage src={line.image ?? ''} alt="" className="cart-line__image" />
      </Link>

      <div className="cart-line__main">
        <Link to={`/products/${line.product_id}`} className="cart-line__name">{line.name}</Link>
        <PriceTag amount={line.price} unit={unitLabel(line.unit)} className="cart-line__price" />
        {!orderable ? <Badge variant="secondary">Unavailable</Badge> : null}
        {short ? (
          <p className="cart-line__warning">{`Only ${quantityLabel(stock, line.unit)} left`}</p>
        ) : null}
        {orderable && (lineMin(line) > 1 || line.max_per_order) ? (
          <p className="cart-line__limit">
            {orderWindowLabel({ min: lineMin(line), max: line.max_per_order, unit: line.unit })}
          </p>
        ) : null}
      </div>

      <QuantityStepper
        value={line.quantity}
        min={lineMin(line)}
        max={Math.max(lineMin(line), Math.min(stock ?? MAX_QUANTITY, lineMax(line)))}
        disabled={!orderable}
        onChange={(quantity) => onQuantityChange(line.product_id, quantity)}
        className="cart-line__stepper"
      />

      <p className="cart-line__amount">
        {orderable ? formatMoney(moneyToNumber(line.price) * line.quantity) : '—'}
      </p>

      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label={`Remove ${line.name}`}
        onClick={() => onRemove(line.product_id)}
      >
        <Trash2 className="cart-line__remove-icon" aria-hidden />
      </Button>
    </li>
  );
}

CartLine.propTypes = {
  line: PropTypes.object.isRequired,
  onQuantityChange: PropTypes.func.isRequired,
  onRemove: PropTypes.func.isRequired,
};
