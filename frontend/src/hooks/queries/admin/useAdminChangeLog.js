import { useQuery } from '@tanstack/react-query';
import { adminApi } from '@/api/admin/adminApi';

export function useAdminChangeLog(model, id, enabled = true) {
  return useQuery({
    queryKey: ['admin', 'change-log', model, id],
    queryFn: () => adminApi.getChangeLog(model, id),
    enabled: enabled && Number.isFinite(id),
  });
}
