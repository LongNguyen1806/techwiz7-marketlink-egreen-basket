import { useQuery } from '@tanstack/react-query';

import { adminApi } from '../../../api/admin/adminApi';
import { QUERY_KEYS } from '@/config/constants';

export function useAdminReports(params) {
  return useQuery({
    queryKey: QUERY_KEYS.ADMIN_REPORTS(params),
    queryFn: () => adminApi.getReports(params),
  });
}

export async function exportAdminReports(params) {
  return adminApi.exportReports(params);
}
