import { useQuery } from '@tanstack/react-query';
import { ordersApi } from '../../../services/customer/ordersApi';
import { QUERY_KEYS } from '../../../constants';


export function useCustomerOrder(orderId) {
  return useQuery({
    queryKey: QUERY_KEYS.ORDER(orderId),
    queryFn: () => ordersApi.detail(orderId),
    enabled: Boolean(orderId),
  });
}
