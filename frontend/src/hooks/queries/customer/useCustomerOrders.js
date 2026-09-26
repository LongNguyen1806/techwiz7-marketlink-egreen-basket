import { useQuery } from '@tanstack/react-query';
import { ordersApi } from '../../../services/customer/ordersApi';
import { QUERY_KEYS } from '../../../constants';

/**
 * CU-05 (C-04). Paginated, and the filters are the server's own: `tab`, `status` (comma separated),
 * `farmer_id`, `pickup_from`, `pickup_to`, `ordering`. Nothing is filtered in the browser, so what a
 * page shows is what the query asked for.
 */
export function useCustomerOrders(params) {
  return useQuery({
    queryKey: QUERY_KEYS.ORDERS(params),
    queryFn: () => ordersApi.list(params),
  });
}
