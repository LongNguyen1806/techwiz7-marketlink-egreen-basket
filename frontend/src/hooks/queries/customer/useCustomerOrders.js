import { useQuery } from '@tanstack/react-query';
import { ordersApi } from '../../../services/customer/ordersApi';
import { QUERY_KEYS } from '../../../constants';


export function useCustomerOrders(params) {
  return useQuery({
    queryKey: QUERY_KEYS.ORDERS(params),
    queryFn: () => ordersApi.list(params),
  });
}
