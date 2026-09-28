import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { farmerApi } from '../../../api/farmer/farmerApi';
import { farmerKeys } from '../../../constants/queryKeys';
import { STALE } from '../../../constants/staleTimes';
import { notify } from '../../../lib/toast';

export const REVIEWS_PAGE_SIZE = 20;


export const reviewKey = (review) => `${review.type}-${review.id}`;

const toPage = (data) => ({
  reviews: data.results,
  total: data.count,
  page: data.page,
  pageSize: data.page_size,
  totalPages: data.total_pages,
});


export function useFarmerReviews(filters) {
  return useQuery({
    queryKey: farmerKeys.reviews.list(filters),
    queryFn: ({ signal }) =>
      farmerApi.getReviews({ ...filters, page: filters.page ?? 1, page_size: REVIEWS_PAGE_SIZE }, { signal }),
    select: toPage,
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
        Array.isArray(data?.results)
          ? { ...data, results: data.results.map((item) => (reviewKey(item) === key ? review : item)) }
          : data,
      );
      notify.success('Reply posted');
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: farmerKeys.reviews.all() }),
  });
}
