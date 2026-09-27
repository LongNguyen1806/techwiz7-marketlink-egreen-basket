import { Link } from 'react-router-dom';
import { ShoppingCart } from 'lucide-react';
import { Button } from '../../ui/Button';
import { cartCount, useCartStore } from '../../../stores/cart.store';
import './MiniCartDrawer.css';

export function MiniCartDrawer() {
  const items = useCartStore((s) => s.lines);
  const count = cartCount(items);

  return (
    <Button asChild variant="ghost" size="icon" aria-label="Cart" className="mini-cart__trigger">
      <Link to="/customer/cart">
        <ShoppingCart className="mini-cart__icon" />
        {count > 0 ? <span className="mini-cart__badge">{count}</span> : null}
      </Link>
    </Button>
  );
}

