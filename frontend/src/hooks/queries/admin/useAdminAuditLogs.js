import { useQuery } from '@tanstack/react-query';
import { adminApi } from '../../../api/admin/adminApi';

export function useAdminAuditLogs(params = {}) {
  return useQuery({
    queryKey: ['admin', 'audit-logs', params],
    queryFn: () => adminApi.getAuditLogs(params),
  });
}
