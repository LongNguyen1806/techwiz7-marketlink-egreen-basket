import { useQuery } from '@tanstack/react-query';

import { adminApi } from '../../../api/admin/adminApi';
import { STALE } from '../../../constants/staleTimes';

const APPROVAL_COUNTS_KEY = ['admin', 'approval-counts'];

export function invalidateApprovalCounts(queryClient) {
  void queryClient.invalidateQueries({ queryKey: APPROVAL_COUNTS_KEY });
}

export function useAdminApprovalCounts() {
  return useQuery({
    queryKey: APPROVAL_COUNTS_KEY,
    queryFn: ({ signal }) => adminApi.getApprovalCounts({ signal }),
    staleTime: STALE.MINUTE,
    refetchInterval: STALE.MINUTE,
  });
}
