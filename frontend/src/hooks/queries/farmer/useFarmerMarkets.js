import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { farmerApi } from '../../../api/farmer/farmerApi';
import { farmerKeys } from '../../../constants/queryKeys';
import { STALE } from '../../../constants/staleTimes';
import { ApiError } from '../../../lib/ApiError';
import { notify, notifyError } from '../../../lib/toast';

// Only the farmer edits these; an admin closing a market or changing its schedule arrives
// as MARKET_CLOSED / MARKET_SCHEDULE_CHANGED and refreshes the list.
export function useFarmerMarkets() {
  return useQuery({
    queryKey: farmerKeys.markets(),
    queryFn: ({ signal }) => farmerApi.getMarkets({ signal }),
    staleTime: STALE.MEDIUM,
  });
}

function replaceMarket(markets, updated) {
  return markets?.map((item) => (item.id === updated.id ? updated : item));
}

function mapSlots(markets, farmerMarketId, mapSlotList) {
  return markets?.map((item) => (item.id === farmerMarketId ? { ...item, slots: mapSlotList(item.slots) } : item));
}

const bySchedule = (a, b) => a.day_of_week - b.day_of_week || a.start_time.localeCompare(b.start_time);

export function useJoinMarket() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: farmerApi.joinMarket,
    onSuccess: (item) => {
      queryClient.setQueryData(farmerKeys.markets(), (markets) =>
        [...(markets ?? []), item].sort((a, b) => a.market.name.localeCompare(b.market.name)),
      );
      notify.success(`You now sell at ${item.market.name}`);
    },
  });
}

export function useUpdateStallLabel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ farmerMarketId, stallLabel }) => farmerApi.updateStallLabel(farmerMarketId, stallLabel),
    onSuccess: (item) => {
      queryClient.setQueryData(farmerKeys.markets(), (markets) => replaceMarket(markets, item));
      notify.success('Stall location saved');
    },
  });
}

// Not optimistic: the server refuses while open orders remain at the market.
export function useLeaveMarket() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ farmerMarketId }) => farmerApi.leaveMarket(farmerMarketId),
    onSuccess: (_data, { farmerMarketId, marketName }) => {
      queryClient.setQueryData(farmerKeys.markets(), (markets) =>
        markets?.filter((item) => item.id !== farmerMarketId),
      );
      notify.success(`You left ${marketName}`);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: farmerKeys.markets() }),
  });
}

export function useCreatePickupSlot() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: farmerApi.createPickupSlot,
    onSuccess: (slot, { farmerMarketId }) => {
      queryClient.setQueryData(farmerKeys.markets(), (markets) =>
        mapSlots(markets, farmerMarketId, (slots) => [...slots, slot].sort(bySchedule)),
      );
      notify.success('Pickup slot added');
    },
  });
}

/**
 * Switches a slot on or off at once, rolled back if refused. Turning a slot back on
 * re-checks the market schedule, so the server's reason is shown instead of the generic
 * "check the highlighted fields" (there is no form here to highlight).
 */
export function useTogglePickupSlot() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ slotId, isActive }) => farmerApi.updatePickupSlot(slotId, { is_active: isActive }),
    meta: { silent: true },
    onMutate: async ({ farmerMarketId, slotId, isActive }) => {
      await queryClient.cancelQueries({ queryKey: farmerKeys.markets() });
      const previous = queryClient.getQueryData(farmerKeys.markets());
      queryClient.setQueryData(farmerKeys.markets(), (markets) =>
        mapSlots(markets, farmerMarketId, (slots) =>
          slots.map((slot) => (slot.id === slotId ? { ...slot, is_active: isActive } : slot)),
        ),
      );
      return { previous };
    },
    onError: (error, _variables, context) => {
      queryClient.setQueryData(farmerKeys.markets(), context?.previous);
      const reason = Object.values(ApiError.fromUnknown(error).fieldErrors).flat()[0];
      notifyError(error, reason ? { title: "This slot can't be turned on", description: reason } : undefined);
    },
    onSuccess: (_slot, { isActive }) => {
      notify.success(isActive ? 'Slot is open for booking' : 'Slot turned off');
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: farmerKeys.markets() }),
  });
}
