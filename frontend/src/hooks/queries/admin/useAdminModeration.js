import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { ApiError } from '@/lib/ApiError';
import { adminApi } from '../../../api/admin/adminApi';
import { QUERY_KEYS } from '@/config/constants';

// A product needs only its id; a review also needs the table its id belongs to.

function invalidateModeration(queryClient) {
  // Only the first key segment, so every sort order of the list is refreshed.
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
      // Which review table the id belongs to decides the route (AD-23 vs AD-24).
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
      // The cancelled orders change what the follow-up counts and the order list show.
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
      // Worded so nobody reads it as an undo: the cancelled orders are not coming back.
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
