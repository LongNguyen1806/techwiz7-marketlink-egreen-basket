import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { ApiError } from '@/lib/ApiError';
import { adminApi } from '../../../api/admin/adminApi';
import { QUERY_KEYS } from '@/config/constants';

// A decision on one listing changes two screens: the product list it belongs to, whatever it
// is filtered by, and the dashboard count that sent the admin here in the first place.
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

/**
 * Approve every listing a stall has waiting, in one action.
 *
 * Sent one after another rather than all at once: each approval writes an audit row and a
 * notification, and a stall with a dozen listings firing a dozen parallel writes is how a
 * deadlock gets found in production rather than here.
 */
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
      // Some may already be through. The list is refetched either way so the screen shows
      // what actually happened rather than what was asked for.
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
