import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { farmerApi } from '../../../api/farmer/farmerApi';
import { authKeys, farmerKeys } from '../../../constants/queryKeys';
import { STALE } from '../../../constants/staleTimes';
import { notify } from '../../../lib/toast';



export function useFarmerProfile() {
  return useQuery({
    queryKey: farmerKeys.profile(),
    queryFn: ({ signal }) => farmerApi.getProfile({ signal }),
    staleTime: STALE.MEDIUM,
  });
}


export function useUpdateFarmerProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: farmerApi.updateProfile,
    onSuccess: ({ deactivated_slot_count: deactivated, ...profile }) => {
      queryClient.setQueryData(farmerKeys.profile(), profile);
      notify.success('Stall profile saved');
      if (deactivated > 0) {
        notify.warning(`${deactivated} pickup slot${deactivated === 1 ? ' was' : 's were'} turned off`, {
          description: 'They fall on days you no longer work. Turn them back on from Markets if needed.',
        });
      }
    },
    onSettled: () => {
      
      void queryClient.invalidateQueries({ queryKey: authKeys.me() });
      void queryClient.invalidateQueries({ queryKey: farmerKeys.markets() });
    },
  });
}
