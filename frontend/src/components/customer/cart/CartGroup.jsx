import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { Store } from 'lucide-react';
import { CartLine } from './CartLine';
import { formatMoney } from '../../../utils/formatters';
import './CartGroup.css';


export function CartGroup({ group, onQuantityChange, onRemove }) {
  const headingId = `cart-group-${group.farmer_id}`;

  return (
    <section className="cart-group" aria-labelledby={headingId}>
      <header className="cart-group__head">
        <Store className="cart-group__icon" aria-hidden />
        <h2 className="cart-group__title" id={headingId}>
          <Link to={`/farmers/${group.farmer_id}`}>{group.farmer_stall_name}</Link>
        </h2>
      </header>

      <ul className="cart-group__lines">
        {group.lines.map((line) => (
          <CartLine
            key={line.product_id}
            line={line}
            onQuantityChange={onQuantityChange}
            onRemove={onRemove}
          />
        ))}
      </ul>

      <p className="cart-group__subtotal">
        <span className="cart-group__subtotal-label">Subtotal</span>
        <span className="cart-group__subtotal-value" data-testid={`cart-subtotal-${group.farmer_id}`}>
          {formatMoney(group.subtotal)}
        </span>
      </p>
    </section>
  );
}

CartGroup.propTypes = {
  group: PropTypes.object.isRequired,
  onQuantityChange: PropTypes.func.isRequired,
  onRemove: PropTypes.func.isRequired,
};
