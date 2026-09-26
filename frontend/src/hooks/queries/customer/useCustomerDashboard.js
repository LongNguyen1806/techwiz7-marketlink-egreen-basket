import { useQuery } from '@tanstack/react-query';
import { customerApi } from '../../../services/customer/customerApi';
import { QUERY_KEYS } from '../../../constants';


export function useCustomerDashboard() {
  return useQuery({
    queryKey: QUERY_KEYS.CUSTOMER_DASHBOARD,
    queryFn: customerApi.dashboard,
    staleTime: 30_000,
  });
}
