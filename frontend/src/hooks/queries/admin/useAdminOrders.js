import { useQuery } from '@tanstack/react-query';

import { adminApi } from '../../../api/admin/adminApi';
import { QUERY_KEYS } from '@/config/constants';

export function useAdminOrders(params = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.ADMIN_ORDERS(params),
    queryFn: () => adminApi.getOrders(params),
    staleTime: 0,
    placeholderData: (previous) => previous,
  });
}

export function useAdminOrder(id) {
  return useQuery({
    queryKey: QUERY_KEYS.ADMIN_ORDER(id),
    queryFn: () => adminApi.getOrder(id),
    enabled: Number.isFinite(id),
  });
}
