import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { ordersApi } from '../../../services/customer/ordersApi';
import { QUERY_KEYS } from '../../../constants';
import { useCartStore } from '../../../stores/cart.store';


export function useCheckout() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const clear = useCartStore((state) => state.clear);

  return useMutation({
    mutationFn: ordersApi.checkout,
    onSuccess: (data) => {
      clear();
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.CUSTOMER_DASHBOARD });
      
      navigate('/customer/checkout/success', { replace: true, state: { orders: data.orders } });
    },
  });
}
