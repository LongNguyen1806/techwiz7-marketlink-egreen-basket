import { useMutation, useQueryClient } from '@tanstack/react-query';
import { reviewsApi } from '../../../services/customer/reviewsApi';
import { QUERY_KEYS } from '../../../constants';

/**
 * CU-10 / CU-11 (C-07). Each review is refused a second time (422 REVIEW_NOT_ALLOWED), so the order
 * is refetched afterwards: `review_state` is what decides which forms are still worth showing.
 */
function useReviewMutation(orderId, mutationFn) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ORDER(orderId) });
    },
  });
}

/** CU-10: the stall behind the order. */
export function useReviewFarmer(orderId) {
  return useReviewMutation(orderId, ({ rating, comment }) =>
    reviewsApi.farmer({ orderId, rating, comment }));
}

/** CU-11: one line, addressed by its order item id. */
export function useReviewItem(orderId) {
  return useReviewMutation(orderId, ({ itemId, rating, comment }) =>
    reviewsApi.item({ orderId, itemId, rating, comment }));
}
