import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { adminApi } from '../../../api/admin/adminApi';
import { QUERY_KEYS } from '@/config/constants';
import { ApiError } from '@/lib/ApiError';

export function useRaiseFlag() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload) => adminApi.raiseFlag(payload),
    onSuccess: () => {
      toast.success('Added to the follow-up queue');
      void queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.ADMIN_FLAGS()[0]] });
      // The dashboard counts open flags, so it is now out of date.
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ADMIN_DASHBOARD });
    },
    onError: (error) => toast.error(ApiError.fromUnknown(error).friendlyMessage),
  });
}
