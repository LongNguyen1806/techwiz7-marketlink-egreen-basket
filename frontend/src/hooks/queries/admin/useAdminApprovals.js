import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { ApiError } from '@/lib/ApiError';
import { adminApi } from '../../../api/admin/adminApi';
import { QUERY_KEYS } from '@/config/constants';

function invalidateApprovals(queryClient) {
  void queryClient.invalidateQueries({
    queryKey: [QUERY_KEYS.ADMIN_MODERATION_PRODUCTS()[0]],
  });
  void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ADMIN_DASHBOARD });
}

export function useApproveProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: adminApi.approveProduct,
    onSuccess: () => {
      toast.success('Listing approved — shoppers can see it now');
      invalidateApprovals(queryClient);
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}

export function useApproveProducts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (ids) => {
      for (const id of ids) {
        await adminApi.approveProduct(id);
      }
      return ids.length;
    },
    onSuccess: (count) => {
      toast.success(`${count} ${count === 1 ? 'listing' : 'listings'} approved`);
      invalidateApprovals(queryClient);
    },
    onError: (e) => {
      invalidateApprovals(queryClient);
      toast.error(ApiError.fromUnknown(e).friendlyMessage);
    },
  });
}

export function useRejectProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }) => adminApi.rejectProduct(id, reason),
    onSuccess: () => {
      toast.success('Listing refused — the stall has been told why');
      invalidateApprovals(queryClient);
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}
