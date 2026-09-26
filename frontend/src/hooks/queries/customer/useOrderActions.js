import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ordersApi } from '../../../services/customer/ordersApi';
import { QUERY_KEYS } from '../../../constants';

/**
 * CU-07 and CU-08 both answer with the whole OrderDetail, so the fresh copy — including its new
 * `version` and `allowed_actions` — is written straight into the cache. The list and the dashboard
 * counts are invalidated because a cancelled or rescheduled order changes both.
 */
function useOrderMutation(orderId, mutationFn) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn,
    onSuccess: (order) => {
      queryClient.setQueryData(QUERY_KEYS.ORDER(orderId), order);
      queryClient.invalidateQueries({ queryKey: ['orders'] });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.CUSTOMER_DASHBOARD });
    },
  });
}

/** CU-08: T5 from PLACED, T6 from ACCEPTED. `If-Match` is the version the screen was showing. */
export function useCancelOrder(orderId) {
  return useOrderMutation(orderId, ({ version, reason }) =>
    ordersApi.cancel({ orderId, version, reason }));
}

/** CU-07: applied at once on a PLACED order, recorded as a change request on an ACCEPTED one (D-030). */
export function useModifyOrder(orderId) {
  return useOrderMutation(orderId, ({ version, body }) =>
    ordersApi.modify({ orderId, version, body }));
}
