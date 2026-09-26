import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { catalogApi } from '../../../api/guest/catalogApi';
import { publicKeys } from '../../../constants/queryKeys';
import { STALE } from '../../../constants/staleTimes';

export function usePublicConfig() {
  return useQuery({
    queryKey: publicKeys.config(),
    queryFn: ({ signal }) => catalogApi.getConfig({ signal }),
    staleTime: STALE.STATIC,
  });
}

export function useCategories() {
  return useQuery({
    queryKey: publicKeys.categories(),
    queryFn: ({ signal }) => catalogApi.getCategories({ signal }),
    staleTime: STALE.STATIC,
  });
}

export function usePublicMarkets(params = {}) {
  return useQuery({
    queryKey: publicKeys.markets(params),
    queryFn: ({ signal }) => catalogApi.getMarkets(params, { signal }),
    staleTime: STALE.LONG,
    placeholderData: keepPreviousData,
  });
}
