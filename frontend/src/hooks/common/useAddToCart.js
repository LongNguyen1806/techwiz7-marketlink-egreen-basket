import { useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ROLES } from '../../constants/roles';
import { ROUTES } from '../../constants/routes';
import { notify } from '../../lib/toast';
import { useCartStore } from '../../stores/cart.store';
import { unitLabel } from '../../utils/labels';
import { useAuth } from '../authentication/useAuth';


export function toCartLine(product) {
  return {
    product_id: product.id,
    farmer_id: product.farmer.id,
    farmer_stall_name: product.farmer.stall_name,
    name: product.name,
    unit: product.unit,
    price: product.price,
    image: product.image,
    min_per_order: product.min_per_order ?? 1,
    max_per_order: product.max_per_order ?? null,
  };
}


export function useAddToCart() {
  const navigate = useNavigate();
  const location = useLocation();
  const { role } = useAuth();
  const addItem = useCartStore((state) => state.addItem);

  const requireSignIn = useCallback(
    () => navigate(ROUTES.LOGIN, { state: { from: location } }),
    [location, navigate],
  );

  const addToCart = useCallback(
    (product, quantity = 1) => {
      if (!role) {
        requireSignIn();
        return false;
      }
      if (role !== ROLES.CUSTOMER) {
        notify.info('Sign in with a shopper account to order');
        return false;
      }
      const inCart = useCartStore.getState().lines.find((line) => line.product_id === product.id)?.quantity ?? 0;
      addItem(toCartLine(product), quantity);
      const minimum = product.min_per_order ?? 1;
      const cap = product.max_per_order;
      if (inCart + quantity < minimum) {
        notify.info(`${product.name}: minimum ${minimum} ${unitLabel(product.unit)} per order`, {
          description: `We added ${minimum} to your cart.`,
        });
        return true;
      }
      if (cap && inCart + quantity > cap) {
        notify.info(`${product.name}: at most ${cap} ${unitLabel(product.unit)} per order`, {
          description: `Your cart now has the maximum of ${cap}.`,
        });
        return true;
      }
      notify.success(`${product.name} added to your cart`);
      return true;
    },
    [addItem, requireSignIn, role],
  );

  return { addToCart, requireSignIn };
}
