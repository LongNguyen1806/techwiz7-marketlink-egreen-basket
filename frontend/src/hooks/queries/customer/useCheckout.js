import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { ordersApi } from '../../../services/customer/ordersApi';
import { QUERY_KEYS } from '../../../constants';
import { useCartStore } from '../../../stores/cart.store';

/**
 * CU-04 (C-02 → C-03). The cart is emptied only after the server has answered 201, so a failed
 * checkout leaves the customer with their cart intact and can simply be tried again.
 */
export function useCheckout() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const clear = useCartStore((state) => state.clear);

  return useMutation({
    mutationFn: ordersApi.checkout,
    onSuccess: (data) => {
      clear();
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.CUSTOMER_DASHBOARD });
      // C-03 reads the created orders from the navigation state; a reload falls back to C-04.
      navigate('/customer/checkout/success', { replace: true, state: { orders: data.orders } });
    },
  });
}
