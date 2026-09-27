import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { ApiError } from '@/lib/ApiError';
import { QUERY_KEYS } from '@/config/constants';
import { STALE } from '@/constants/staleTimes';
import { adminApi } from '../../../api/admin/adminApi';

// A re-run changes the queue row it belongs to and the agreement figures.
function invalidateAIViews(queryClient) {
  void queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.ADMIN_MODERATION_PRODUCTS()[0]] });
  void queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.ADMIN_AI_REVIEW_STATS()[0]] });
}

/** How the AI's advice compared with admin decisions over the last `days` days. */
export function useAIReviewStats(days = 30) {
  return useQuery({
    queryKey: QUERY_KEYS.ADMIN_AI_REVIEW_STATS(days),
    queryFn: ({ signal }) => adminApi.getAIReviewStats(days, { signal }),
    staleTime: STALE.MINUTE,
    placeholderData: keepPreviousData,
  });
}

export function useAIRecheck() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: adminApi.recheckProductWithAI,
    // The model can take several seconds; the row shows its own spinner meanwhile.
    onSuccess: (product) => {
      const verdict = product?.ai_review?.verdict;
      toast.success(verdict ? `AI review finished: ${verdict.replaceAll('_', ' ').toLowerCase()}` : 'AI review finished');
      invalidateAIViews(queryClient);
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
    meta: { silent: true },
  });
}

export function usePriceGuidelines() {
  return useQuery({
    queryKey: QUERY_KEYS.ADMIN_PRICE_GUIDELINES,
    queryFn: ({ signal }) => adminApi.getPriceGuidelines({ signal }),
    staleTime: STALE.MEDIUM,
  });
}

/** Create or update one guideline. Silent: the form shows field errors itself. */
export function useSavePriceGuideline() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }) =>
      id ? adminApi.updatePriceGuideline(id, payload) : adminApi.createPriceGuideline(payload),
    meta: { silent: true },
    onSuccess: (_saved, { id }) => {
      toast.success(id ? 'Guideline saved' : 'Guideline added');
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ADMIN_PRICE_GUIDELINES });
    },
  });
}

export function useDeletePriceGuideline() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: adminApi.deletePriceGuideline,
    onSuccess: () => {
      toast.success('Guideline removed');
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ADMIN_PRICE_GUIDELINES });
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}
