import { keepPreviousData, useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { farmerApi } from '../../../api/farmer/farmerApi';
import { farmerKeys } from '../../../constants/queryKeys';
import { STALE } from '../../../constants/staleTimes';
import { notify } from '../../../lib/toast';

export const REVIEWS_PAGE_SIZE = 20;


export const reviewKey = (review) => `${review.type}-${review.id}`;

const flattenPages = (data) => ({
  reviews: data.pages.flatMap((page) => page.results),
  total: data.pages[0]?.count ?? 0,
});


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
