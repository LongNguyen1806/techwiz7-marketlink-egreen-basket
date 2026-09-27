import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query';

import { ApiError } from '@/lib/ApiError';
import { notifyError } from '@/lib/toast';
import { STALE } from '@/config/constants';

// A 4xx is an answer, not a hiccup: asking again gets the same refusal and only delays the
// message. Anything else gets two more tries.
function shouldRetry(failureCount, error) {
  const { status } = ApiError.fromUnknown(error);
  if (status >= 400 && status < 500) return false;
  return failureCount < 2;
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error, query) => {
      // A background refetch that fails while data is already on screen stays quiet; the
      // screen is still showing something true. A first load that fails has nothing to show,
      // so it says so.
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
      // Nothing is served from cache unless a query opts in with its own staleTime. An admin
      // acting on a list has to be looking at what the server holds, not at a copy from
      // thirty seconds ago that their own last action already invalidated.
      staleTime: STALE.LIVE,
      retry: shouldRetry,
      refetchOnWindowFocus: true,
    },
    mutations: {
      retry: false,
    },
  },
});
