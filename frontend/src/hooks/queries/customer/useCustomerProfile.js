import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { customerApi } from '../../../services/customer/customerApi';
import { QUERY_KEYS, authKeys } from '../../../constants';


export function useCustomerProfile() {
  return useQuery({
    queryKey: QUERY_KEYS.CUSTOMER_PROFILE,
    queryFn: customerApi.profile,
  });
}


export function useUpdateCustomerProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: customerApi.updateProfile,
    onSuccess: (profile) => {
      queryClient.setQueryData(QUERY_KEYS.CUSTOMER_PROFILE, profile);
      queryClient.invalidateQueries({ queryKey: authKeys.me() });
      toast.success('Profile saved');
    },
  });
}
