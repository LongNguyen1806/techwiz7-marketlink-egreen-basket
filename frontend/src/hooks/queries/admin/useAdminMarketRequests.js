import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { ApiError } from '../../../lib/ApiError';
import { adminApi } from '../../../api/admin/adminApi';
import { invalidateApprovalCounts } from './useAdminApprovalCounts';

const MARKET_REQUESTS_KEY = ['admin', 'market-requests'];

function invalidateMarketRequests(queryClient) {
  queryClient.invalidateQueries({ queryKey: MARKET_REQUESTS_KEY });
  queryClient.invalidateQueries({ queryKey: ['admin', 'farmer'] });
  queryClient.invalidateQueries({ queryKey: ['admin', 'farmers'] });
  queryClient.invalidateQueries({ queryKey: ['admin-dashboard'] });
  invalidateApprovalCounts(queryClient);
}

export function useAdminMarketRequests(params = {}) {
  return useQuery({
    queryKey: [...MARKET_REQUESTS_KEY, params],
    queryFn: () => adminApi.getMarketRequests(params),
    staleTime: 0,
    placeholderData: (previous) => previous,
  });
}

export function useApproveMarketRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: adminApi.approveMarketRequest,
    onSuccess: () => {
      toast.success('Market approved for this stall');
      invalidateMarketRequests(queryClient);
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}

export function useRejectMarketRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }) => adminApi.rejectMarketRequest(id, reason),
    onSuccess: () => {
      toast.success('Market request refused');
      invalidateMarketRequests(queryClient);
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}
