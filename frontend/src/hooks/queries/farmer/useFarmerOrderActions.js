import { useMutation, useQueryClient } from '@tanstack/react-query';
import { farmerApi } from '../../../api/farmer/farmerApi';
import { farmerKeys } from '../../../constants/queryKeys';
import { notify } from '../../../lib/toast';

export const ORDER_ACTIONS = Object.freeze({
  ACCEPT: 'ACCEPT',
  DECLINE: 'DECLINE',
  READY: 'READY',
  COMPLETE: 'COMPLETE',
  NO_SHOW: 'NO_SHOW',
  MARK_ITEM_SOLD_OUT: 'MARK_ITEM_SOLD_OUT',
  APPROVE_CHANGE: 'APPROVE_CHANGE',
  REJECT_CHANGE: 'REJECT_CHANGE',
});

const A = ORDER_ACTIONS;

/**
 * Actions the farmer may take now. The detail endpoint sends `allowed_actions`; list rows
 * do not, so the same rules as the backend (FarmerOrderDetailSerializer.get_allowed_actions)
 * are applied to the summary fields. The server still has the final say.
 */
export function allowedOrderActions(order, now = Date.now()) {
  if (Array.isArray(order.allowed_actions)) return order.allowed_actions;

  const pickupStart = new Date(order.pickup_start_at).getTime();
  const pickupEnd = new Date(order.pickup_end_at).getTime();
  const cutoff = new Date(order.cutoff_at).getTime();
  const actions = [];

  if (order.status === 'PLACED' && now < pickupStart) {
    actions.push(A.ACCEPT, A.DECLINE);
    if (order.item_count > 1) actions.push(A.MARK_ITEM_SOLD_OUT);
  } else if (order.status === 'ACCEPTED') {
    if (order.has_pending_change) {
      if (now < pickupStart) actions.push(A.APPROVE_CHANGE, A.REJECT_CHANGE, A.DECLINE);
    } else {
      if (now >= cutoff) actions.push(A.READY);
      if (now < pickupStart) actions.push(A.DECLINE);
      if (now >= pickupEnd) actions.push(A.NO_SHOW);
    }
  } else if (order.status === 'READY_FOR_PICKUP') {
    actions.push(A.COMPLETE);
    if (now >= pickupEnd) actions.push(A.NO_SHOW);
  }
  return actions;
}

const SUCCESS_MESSAGES = {
  [A.ACCEPT]: 'Order accepted',
  [A.DECLINE]: 'Order declined',
  [A.READY]: 'Marked ready for pickup',
  [A.COMPLETE]: 'Pickup completed',
  [A.NO_SHOW]: 'Marked as no-show',
};

function runAction({ action, order, reason, soldOutProductIds }) {
  const { id, version } = order;
  switch (action) {
    case A.ACCEPT:
      return farmerApi.acceptOrder(id, version);
    case A.DECLINE:
      return farmerApi.declineOrder(id, version, { reason, soldOutProductIds });
    case A.READY:
      return farmerApi.markOrderReady(id, version);
    case A.COMPLETE:
      return farmerApi.completeOrder(id, version);
    case A.NO_SHOW:
      return farmerApi.markOrderNoShow(id, version);
    default:
      return Promise.reject(new Error(`Unsupported order action: ${action}`));
  }
}

// Wording when the order moved on before the action reached the server.
const STALE_ORDER = {
  title: 'This order was just updated',
  description: "We've loaded its latest details. Check them and try again.",
};

/**
 * Status actions on one order. Not optimistic: every action can be refused by time rules
 * or a newer version, so the UI waits for the server and then shows its answer.
 * mutate({ action, order, reason?, soldOutProductIds? })
 */
export function useFarmerOrderAction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: runAction,
    meta: {
      errorMessages: {
        RESOURCE_MODIFIED: STALE_ORDER,
        INVALID_STATUS_TRANSITION: STALE_ORDER,
      },
    },
    onSuccess: (updatedOrder, { action }) => {
      // The response is the full order detail: show it without another request.
      queryClient.setQueryData(farmerKeys.orders.detail(updatedOrder.id), updatedOrder);
      notify.success(SUCCESS_MESSAGES[action] ?? 'Order updated');
    },
    onError: (_error, { order }) => {
      void queryClient.invalidateQueries({ queryKey: farmerKeys.orders.detail(order.id) });
    },
    onSettled: () => {
      // A status change moves the order between tabs and changes counts, the prep list,
      // held stock and the dashboard figures.
      [
        farmerKeys.orders.lists(),
        farmerKeys.orders.tabCounts(),
        farmerKeys.orders.pickingLists(),
        farmerKeys.products.all(),
        farmerKeys.dashboard.all(),
      ].forEach((queryKey) => void queryClient.invalidateQueries({ queryKey }));
    },
  });
}
