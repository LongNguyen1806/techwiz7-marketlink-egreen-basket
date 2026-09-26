import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { ApiError } from '@/lib/ApiError';
import { adminApi } from '@/api/admin/adminApi';

function invalidateMarkets(queryClient) {
  return queryClient.invalidateQueries({
    queryKey: ['admin', 'markets'],
  });
}

export function useAdminMarkets(params = {}) {
  return useQuery({
    queryKey: ['admin', 'markets', params],
    queryFn: () => adminApi.getMarkets(params),
  });
}

export function useAdminMarket(id, enabled = true) {
  return useQuery({
    queryKey: ['admin', 'market', id],
    queryFn: () => adminApi.getMarket(id),
    enabled: enabled && Number.isFinite(id),
  });
}

export function useToggleAdminMarket() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, active, reason }) => {
      if (active) return adminApi.activateMarket(id);
      return adminApi.deactivateMarket(id, reason ?? '');
    },
    onSuccess: (data, vars) => {
      if (vars.active) {
        toast.success('Market reopened');
      } else {
        const cancelled = data?.cancelled_orders ?? 0;
        toast.success(
          cancelled
            ? `Market closed. ${cancelled} open order${cancelled === 1 ? '' : 's'} cancelled.`
            : 'Market closed',
        );
      }
      void invalidateMarkets(queryClient);
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}

export function useSaveAdminMarket(marketId) {
  const queryClient = useQueryClient();
  const isEdit = marketId !== undefined && Number.isFinite(marketId);

  return useMutation({
    mutationFn: async (payload) => {
      if (isEdit && marketId !== undefined) {
        return adminApi.updateMarket(marketId, payload);
      }
      return adminApi.createMarket(payload);
    },
    onSuccess: () => {
      toast.success(isEdit ? 'Market updated' : 'Market created');
      void invalidateMarkets(queryClient);
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}

export function useMarketClosures(marketId, enabled) {
  return useQuery({
    queryKey: ['admin', 'market-closures', marketId],
    queryFn: () => adminApi.getMarketClosures(marketId),
    enabled: Boolean(enabled),
  });
}

export function useCreateMarketClosure(marketId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload) => adminApi.createMarketClosure(marketId, payload),
    onSuccess: () => {
      toast.success('Closure period added');
      void queryClient.invalidateQueries({
        queryKey: ['admin', 'market-closures', marketId],
      });
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}

export function useDeleteMarketClosure(marketId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: adminApi.deleteMarketClosure,
    onSuccess: () => {
      toast.success('Closure period removed');
      void queryClient.invalidateQueries({
        queryKey: ['admin', 'market-closures', marketId],
      });
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}
