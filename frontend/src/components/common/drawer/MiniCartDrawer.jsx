import { Link } from 'react-router-dom';
import { ShoppingCart } from 'lucide-react';
import { Button } from '../../ui/Button';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '../../ui/Sheet';
import { formatMoney } from '../../../utils/formatters';
import { moneyToNumber } from '../../../utils/helpers/domain';
import { cartCount, cartGroups, cartTotal, useCartStore } from '../../../stores/cart.store';
import './MiniCartDrawer.css';
export function MiniCartDrawer() {
    const items = useCartStore((s) => s.lines);
    const count = cartCount(items);
    const total = cartTotal(items);
    const groups = cartGroups(items);
    return (<Sheet>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Cart" className="mini-cart__trigger">
          <ShoppingCart className="mini-cart__icon"/>
          {count > 0 ? <span className="mini-cart__badge">{count}</span> : null}
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="mini-cart__sheet">
        <SheetHeader>
          <SheetTitle>Your cart ({count})</SheetTitle>
        </SheetHeader>
        <div className="mini-cart__list">
          {groups.map((group) => (<div key={group.farmer_id} className="mini-cart__group">
              <p className="mini-cart__group-title">{group.farmer_stall_name}</p>
              <ul className="mini-cart__items">
                {group.lines.map((item) => (<li key={item.product_id} className="mini-cart__line">
                    <span className="mini-cart__line-name">
                      {item.quantity}× {item.name}
                    </span>
                    <span className="mini-cart__line-price">
                      {formatMoney(moneyToNumber(item.price) * item.quantity)}
                    </span>
                  </li>))}
              </ul>
            </div>))}
          {items.length === 0 ? (<p className="mini-cart__empty">Nothing reserved yet — add produce to get started.</p>) : null}
        </div>
        <div className="mini-cart__footer">
          <div className="mini-cart__total">
            <span>Subtotal</span>
            <span>{formatMoney(total)}</span>
          </div>
          <Button asChild className="mini-cart__checkout-btn" disabled={items.length === 0}>
            <Link to="/customer/cart">Review cart</Link>
          </Button>
        </div>
      </SheetContent>
    </Sheet>);
}
