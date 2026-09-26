import { Link } from 'react-router-dom';
import { ArrowRight, ShoppingBasket } from 'lucide-react';
import { CartGroup } from '../../components/customer/cart/CartGroup';
import { PageHeader } from '../../components/common/PageHeader';
import { Button } from '../../components/ui/Button';
import { useCartRefresh } from '../../hooks/queries/customer/useCartRefresh';
import { cartGroups, cartTotal, isOrderable, useCartStore, MAX_FARMERS_PER_CHECKOUT } from '../../stores/cart.store';
import { formatMoney } from '../../utils/formatters';
import '../../styles/customer/CartPage.css';

/**
 * C-01 (D-004). The cart is client-side only; opening this page is what brings it back in line with
 * the catalogue (PU-10), so a price change or a sell-out is seen here rather than at checkout.
 */
export default function CartPage() {
  const lines = useCartStore((state) => state.lines);
  const setQuantity = useCartStore((state) => state.setQuantity);
  const removeItem = useCartStore((state) => state.removeItem);
  useCartRefresh();

  const groups = cartGroups(lines);
  const total = cartTotal(lines);
  const orderable = lines.filter(isOrderable);
  const tooManyFarmers = groups.filter((group) => group.lines.some(isOrderable)).length > MAX_FARMERS_PER_CHECKOUT;

  if (lines.length === 0) {
    return (
      <section className="cart-page">
        <PageHeader title="My cart" />
        <div className="cart-page__empty">
          <ShoppingBasket className="cart-page__empty-icon" aria-hidden />
          <p className="cart-page__empty-title">Your cart is empty</p>
          <Button asChild>
            <Link to="/products">Browse products</Link>
          </Button>
        </div>
      </section>
    );
  }

  return (
    <section className="cart-page">
      <PageHeader
        title="My cart"
        description="One order per stall — each stall confirms and hands over its own items."
      />

      <div className="cart-page__groups">
        {groups.map((group) => (
          <CartGroup
            key={group.farmer_id}
            group={group}
            onQuantityChange={setQuantity}
            onRemove={removeItem}
          />
        ))}
      </div>

      <aside className="cart-page__summary">
        <p className="cart-page__total">
          <span>Total</span>
          <span className="cart-page__total-value" data-testid="cart-total">{formatMoney(total)}</span>
        </p>
        <p className="cart-page__note">Pay in cash when you pick up at the market.</p>
        {tooManyFarmers ? (
          <p className="cart-page__warning">
            {`A checkout covers at most ${MAX_FARMERS_PER_CHECKOUT} stalls. Remove some lines and order the rest separately.`}
          </p>
        ) : null}
        <Button asChild size="lg" disabled={orderable.length === 0 || tooManyFarmers}>
          <Link to="/customer/checkout">
            Checkout
            <ArrowRight className="cart-page__cta-icon" aria-hidden />
          </Link>
        </Button>
      </aside>
    </section>
  );
}
