import { useQuery } from '@tanstack/react-query';
import { customerApi } from '../../../services/customer/customerApi';
import { QUERY_KEYS } from '../../../constants';

/**
 * CU-01 (C-00). The endpoint sweeps the customer's overdue orders before counting (D-009), so this
 * is refetched on focus rather than cached for long: an order can expire while the tab sits open.
 */
export function useCustomerDashboard() {
  return useQuery({
    queryKey: QUERY_KEYS.CUSTOMER_DASHBOARD,
    queryFn: customerApi.dashboard,
    staleTime: 30_000,
  });
}
