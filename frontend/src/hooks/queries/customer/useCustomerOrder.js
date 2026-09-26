import { useQuery } from '@tanstack/react-query';
import { ordersApi } from '../../../services/customer/ordersApi';
import { QUERY_KEYS } from '../../../constants';

/** CU-06 (C-05, C-06, C-07). Carries `version` for If-Match and `allowed_actions` for the buttons. */
export function useCustomerOrder(orderId) {
  return useQuery({
    queryKey: QUERY_KEYS.ORDER(orderId),
    queryFn: () => ordersApi.detail(orderId),
    enabled: Boolean(orderId),
  });
}
