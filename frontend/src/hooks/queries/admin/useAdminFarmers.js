import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { ApiError } from '@/lib/ApiError';
import { adminApi } from '@/api/admin/adminApi';

function invalidateFarmers(queryClient) {
  void queryClient.invalidateQueries({
    queryKey: ['admin', 'farmers'],
  });
  void queryClient.invalidateQueries({ queryKey: ['admin', 'dashboard'] });
}

export function useAdminFarmers(params = {}) {
  return useQuery({
    queryKey: ['admin', 'farmers', params],
    queryFn: () => adminApi.getFarmers(params),
  });
}

export function useAdminFarmer(id, enabled = true) {
  return useQuery({
    queryKey: ['admin', 'farmer', id],
    queryFn: () => adminApi.getFarmer(id),
    enabled: enabled && Number.isFinite(id),
  });
}

export function useAdminFarmerImpact(id, enabled = false) {
  return useQuery({
    queryKey: ['admin', 'farmer-impact', id],
    queryFn: () => adminApi.getFarmerImpact(id),
    enabled: enabled && Number.isFinite(id),
  });
}

export function useApproveFarmer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: adminApi.approveFarmer,
    onSuccess: () => {
      toast.success('Stall approved');
      invalidateFarmers(queryClient);
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}

export function useRejectFarmer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }) => adminApi.rejectFarmer(id, reason),
    onSuccess: () => {
      toast.success('Application declined');
      invalidateFarmers(queryClient);
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}

export function useSuspendFarmer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }) => adminApi.suspendFarmer(id, reason),
    onSuccess: () => {
      toast.success('Stall suspended');
      invalidateFarmers(queryClient);
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}

export function useReinstateFarmer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: adminApi.reinstateFarmer,
    onSuccess: () => {
      toast.success('Stall restored');
      invalidateFarmers(queryClient);
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}

export function fetchFarmerImpact(id) {
  return adminApi.getFarmerImpact(id);
}

export function useUpdateFarmer(id) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload) => adminApi.updateFarmer(id, payload),
    onSuccess: () => {
      toast.success('Stall updated');
      invalidateFarmers(queryClient);
      void queryClient.invalidateQueries({ queryKey: ['admin', 'farmer', id] });
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}
