import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { ApiError } from '@/lib/ApiError';
import { adminApi } from '../../../api/admin/adminApi';
import { QUERY_KEYS } from '@/config/constants';

function invalidateModeration(queryClient) {
  void queryClient.invalidateQueries({
    queryKey: [QUERY_KEYS.ADMIN_MODERATION_PRODUCTS()[0]],
  });
  void queryClient.invalidateQueries({
    queryKey: [QUERY_KEYS.ADMIN_MODERATION_REVIEWS()[0]],
  });
}

export function useModerationProducts(params = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.ADMIN_MODERATION_PRODUCTS(params),
    queryFn: () => adminApi.getModerationProducts(params),
  });
}

export function useModerationReviews(params = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.ADMIN_MODERATION_REVIEWS(params),
    queryFn: () => adminApi.getModerationReviews(params),
  });
}

export function useHideModerationItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input) => {
      if (input.type === 'product') {
        return adminApi.hideProduct(input.id, input.reason);
      }
      return adminApi.hideReview(input.id, input.reviewType, input.reason);
    },
    onSuccess: () => {
      toast.success('Content hidden from shoppers');
      invalidateModeration(queryClient);
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}

export function useRestoreModerationProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: adminApi.restoreProduct,
    onSuccess: () => {
      toast.success('Content restored');
      void queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.ADMIN_MODERATION_PRODUCTS()[0]],
      });
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}

export function useBlockModerationProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input) => adminApi.blockProduct(input.id, input.reason),
    onSuccess: (data) => {
      const count = data?.affected_orders ?? 0;
      toast.success(
        count === 0
          ? 'Product taken down'
          : `Product taken down · ${count} ${count === 1 ? 'order' : 'orders'} cancelled`,
      );
      invalidateModeration(queryClient);
      void queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.ADMIN_ORDERS()[0]] });
      void queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.ADMIN_DASHBOARD[0]] });
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}

export function useUnblockModerationProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: adminApi.unblockProduct,
    onSuccess: () => {
      toast.success('Product is on sale again. Cancelled orders were not reinstated.');
      void queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.ADMIN_MODERATION_PRODUCTS()[0]],
      });
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}

export function useRestoreModerationReview() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input) => adminApi.restoreReview(input.id, input.reviewType),
    onSuccess: () => {
      toast.success('Content restored');
      void queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.ADMIN_MODERATION_REVIEWS()[0]],
      });
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}
