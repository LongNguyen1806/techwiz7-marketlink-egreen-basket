import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { ApiError } from '@/lib/ApiError';
import { QUERY_KEYS } from '@/config/constants';
import { adminApi } from '../../../api/admin/adminApi';

const KEY = ['admin', 'ai-decisions'];

function refresh(queryClient) {
  void queryClient.invalidateQueries({ queryKey: KEY });
  void queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.ADMIN_AI_REVIEW_STATS()[0]] });
  void queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.ADMIN_MODERATION_PRODUCTS()[0]] });
}

export function useAIDecisions(params) {
  return useQuery({
    queryKey: [...KEY, params],
    queryFn: ({ signal }) => adminApi.getAIDecisions(params, { signal }),
    staleTime: 0,
    placeholderData: keepPreviousData,
  });
}

export function useCheckAIDecision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id) => adminApi.checkAIDecision(id),
    onSuccess: () => {
      toast.success('Marked as checked');
      refresh(queryClient);
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}

export function useOverrideAIDecision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ productId, approve, reason }) =>
      approve ? adminApi.approveProduct(productId) : adminApi.rejectProduct(productId, reason),
    onSuccess: (_, vars) => {
      toast.success(vars.approve ? 'Listing approved' : 'Listing taken off sale');
      refresh(queryClient);
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}
