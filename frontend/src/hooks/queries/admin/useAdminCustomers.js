import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { ApiError } from '@/lib/ApiError';
import { adminApi } from '@/api/admin/adminApi';

function invalidateCustomers(queryClient) {
  return queryClient.invalidateQueries({
    queryKey: ['admin', 'customers'],
  });
}

export function useAdminCustomers(params = {}) {
  return useQuery({
    queryKey: ['admin', 'customers', params],
    queryFn: () => adminApi.getCustomers(params),
  });
}

export function useDeactivateCustomer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }) => adminApi.deactivateCustomer(id, reason),
    onSuccess: () => {
      toast.success('Account locked');
      void invalidateCustomers(queryClient);
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}

export function useActivateCustomer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id) => adminApi.activateCustomer(id),
    onSuccess: () => {
      toast.success('Account unlocked');
      void invalidateCustomers(queryClient);
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}

export function fetchCustomerImpact(id) {
  return adminApi.getCustomerImpact(id);
}

export function useAdminCustomer(id) {
  return useQuery({
    queryKey: ['admin', 'customer', id],
    queryFn: () => adminApi.getCustomer(id),
    enabled: Boolean(id) && Number.isFinite(id),
  });
}

export function useUpdateCustomer(id) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload) => adminApi.updateCustomer(id, payload),
    onSuccess: () => {
      toast.success('Customer updated');
      void invalidateCustomers(queryClient);
      void queryClient.invalidateQueries({ queryKey: ['admin', 'customer', id] });
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}
