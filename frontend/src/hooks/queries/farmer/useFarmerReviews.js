import { keepPreviousData, useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { farmerApi } from '../../../api/farmer/farmerApi';
import { farmerKeys } from '../../../constants/queryKeys';
import { STALE } from '../../../constants/staleTimes';
import { notify } from '../../../lib/toast';

export const REVIEWS_PAGE_SIZE = 20;

// Stall and product reviews come from two tables, so an id alone is not unique.
export const reviewKey = (review) => `${review.type}-${review.id}`;

const flattenPages = (data) => ({
  reviews: data.pages.flatMap((page) => page.results),
  total: data.pages[0]?.count ?? 0,
});

/** filters: { type, rating, replied }. New reviews arrive slowly, so a minute is fresh enough. */
export function useFarmerReviews(filters) {
  return useInfiniteQuery({
    queryKey: farmerKeys.reviews.list(filters),
    queryFn: ({ pageParam, signal }) =>
      farmerApi.getReviews({ ...filters, page: pageParam, page_size: REVIEWS_PAGE_SIZE }, { signal }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => lastPage.next ?? undefined,
    select: flattenPages,
    placeholderData: keepPreviousData,
    staleTime: STALE.MINUTE,
  });
}

export function useReplyToReview() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: farmerApi.replyToReview,
    onSuccess: (review) => {
      // Show the reply in place at once; the refetch then moves it between filters.
      const key = reviewKey(review);
      queryClient.setQueriesData({ queryKey: farmerKeys.reviews.all() }, (data) =>
        data?.pages
          ? {
              ...data,
              pages: data.pages.map((page) => ({
                ...page,
                results: page.results.map((item) => (reviewKey(item) === key ? review : item)),
              })),
            }
          : data,
      );
      notify.success('Reply posted');
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: farmerKeys.reviews.all() }),
  });
}
