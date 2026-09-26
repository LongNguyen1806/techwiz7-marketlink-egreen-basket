import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query';
import { STALE } from '../constants/staleTimes';
import { ApiError } from './ApiError';
import { notifyError } from './toast';

function shouldRetry(failureCount, error) {
  const { status } = ApiError.fromUnknown(error);
  if (status >= 400 && status < 500) return false;
  return failureCount < 2;
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error, query) => {
      if (query.meta?.silent || query.state.data === undefined) return;
      notifyError(error);
    },
  }),
  mutationCache: new MutationCache({
    onError: (error, _variables, _context, mutation) => {
      if (mutation.meta?.silent) return;
      const apiError = ApiError.fromUnknown(error);
      notifyError(apiError, mutation.meta?.errorMessages?.[apiError.code]);
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: STALE.SEARCH,
      retry: shouldRetry,
      refetchOnWindowFocus: true,
    },
    mutations: {
      retry: false,
    },
  },
});
