import { useMutation, useQueryClient } from '@tanstack/react-query';
import { reviewsApi } from '../../../services/customer/reviewsApi';
import { QUERY_KEYS } from '../../../constants';


function useReviewMutation(orderId, mutationFn) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ORDER(orderId) });
    },
  });
}


export function useReviewFarmer(orderId) {
  return useReviewMutation(orderId, ({ rating, comment }) =>
    reviewsApi.farmer({ orderId, rating, comment }));
}


export function useReviewItem(orderId) {
  return useReviewMutation(orderId, ({ itemId, rating, comment }) =>
    reviewsApi.item({ orderId, itemId, rating, comment }));
}
