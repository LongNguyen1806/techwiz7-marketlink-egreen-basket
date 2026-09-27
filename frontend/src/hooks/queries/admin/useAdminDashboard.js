import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { ApiError } from '@/lib/ApiError';
import { adminApi } from '../../../api/admin/adminApi';
import { QUERY_KEYS } from '@/config/constants';

export function useAdminOrdersByMonth(month) {
  return useQuery({
    queryKey: QUERY_KEYS.ADMIN_ORDERS_BY_MONTH(month),
    queryFn: () => adminApi.getOrdersByMonth(month),
    // The previous month stays on screen while the next one loads, so stepping through the
    // year does not blank the card on every click.
    placeholderData: (previous) => previous,
  });
}

export function useAdminDashboard() {
  return useQuery({
    queryKey: QUERY_KEYS.ADMIN_DASHBOARD,
    queryFn: adminApi.getDashboard,
  });
}

export function useDashboardApproveFarmer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: adminApi.approveFarmer,
    onSuccess: () => {
      toast.success('Stall approved');
      void queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.ADMIN_DASHBOARD,
      });
      void queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.ADMIN_FARMERS()[0]],
      });
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}

export function useDashboardRejectFarmer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id) =>
      adminApi.rejectFarmer(id, 'Profile incomplete — please provide more information.'),
    onSuccess: () => {
      toast.success('Application declined');
      void queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.ADMIN_DASHBOARD,
      });
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}
