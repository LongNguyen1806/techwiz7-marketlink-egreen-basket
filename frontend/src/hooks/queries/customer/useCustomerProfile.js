import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { customerApi } from '../../../services/customer/customerApi';
import { QUERY_KEYS } from '../../../constants';

/** CU-02 (C-10). */
export function useCustomerProfile() {
  return useQuery({
    queryKey: QUERY_KEYS.CUSTOMER_PROFILE,
    queryFn: customerApi.profile,
  });
}

/** CU-03. `full_name` is what /auth/me/ reports as `display_name`, so the header has to be told. */
export function useUpdateCustomerProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: customerApi.updateProfile,
    onSuccess: (profile) => {
      queryClient.setQueryData(QUERY_KEYS.CUSTOMER_PROFILE, profile);
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ME });
      toast.success('Profile saved');
    },
  });
}
