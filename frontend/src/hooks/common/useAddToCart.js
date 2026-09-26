import { useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ROLES } from '../../constants/roles';
import { ROUTES } from '../../constants/routes';
import { notify } from '../../lib/toast';
import { useCartStore } from '../../stores/cart.store';
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
      addItem(toCartLine(product), quantity);
      notify.success(`${product.name} added to your cart`);
      return true;
    },
    [addItem, requireSignIn, role],
  );

  return { addToCart, requireSignIn };
}
