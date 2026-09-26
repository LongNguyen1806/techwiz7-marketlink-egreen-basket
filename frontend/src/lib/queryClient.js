import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query';
import { STALE } from '../constants/staleTimes';
import { ApiError } from './ApiError';
import { notifyError } from './toast';

// A 4xx answer will not change on retry; network blips and 5xx get two more tries.
function shouldRetry(failureCount, error) {
  const { status } = ApiError.fromUnknown(error);
  if (status >= 400 && status < 500) return false;
  return failureCount < 2;
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error, query) => {
      // A first load that fails is shown by the page's own error state. A toast is only
      // needed when a background refetch fails while older data is still on screen.
      if (query.meta?.silent || query.state.data === undefined) return;
      notifyError(error);
    },
  }),
  mutationCache: new MutationCache({
    // One place shows mutation errors. A hook can reword a code for its context with
    // meta.errorMessages = { CODE: { title, description } }, or opt out with meta.silent.
    onError: (error, _variables, _context, mutation) => {
      if (mutation.meta?.silent) return;
      const apiError = ApiError.fromUnknown(error);
      notifyError(apiError, mutation.meta?.errorMessages?.[apiError.code]);
    },
  }),
  defaultOptions: {
    queries: {
      // Hooks set their own staleTime by data type; the default is the safe choice.
      staleTime: STALE.SEARCH,
      retry: shouldRetry,
      refetchOnWindowFocus: true,
    },
    mutations: {
      retry: false,
    },
  },
});
