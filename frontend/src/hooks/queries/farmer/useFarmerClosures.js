import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { farmerApi } from '../../../api/farmer/farmerApi';
import { farmerKeys, publicKeys } from '../../../constants/queryKeys';
import { STALE } from '../../../constants/staleTimes';
import { notify } from '../../../lib/toast';

const byStartDate = (a, b) => a.start_date.localeCompare(b.start_date) || a.id - b.id;

const invalidatePublicStall = (queryClient) =>
  queryClient.invalidateQueries({ queryKey: [...publicKeys.all(), 'farmers'] });

export function useFarmerClosures() {
  return useQuery({
    queryKey: farmerKeys.closures(),
    queryFn: ({ signal }) => farmerApi.getClosures({ signal }),
    staleTime: STALE.MEDIUM,
  });
}

export function useCreateClosure() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: farmerApi.createClosure,
    meta: { silent: true },
    onSuccess: (closure) => {
      queryClient.setQueryData(farmerKeys.closures(), (closures) => [...(closures ?? []), closure].sort(byStartDate));
      notify.success('Time off added');
      void invalidatePublicStall(queryClient);
    },
  });
}

export function useDeleteClosure() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ closureId }) => farmerApi.deleteClosure(closureId),
    onSuccess: (_data, { closureId }) => {
      queryClient.setQueryData(farmerKeys.closures(), (closures) =>
        closures?.filter((closure) => closure.id !== closureId),
      );
      notify.success('Time off removed');
      void invalidatePublicStall(queryClient);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: farmerKeys.closures() }),
  });
}
