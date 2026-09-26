import { useQuery } from '@tanstack/react-query';
import { pickupApi } from '../../../services/customer/pickupApi';
import { QUERY_KEYS } from '../../../constants';

/** PU-08 for one stall (C-02, C-06). A window can pass its cut-off while the page is open. */
export function usePickupOptions(farmerId) {
  return useQuery({
    queryKey: QUERY_KEYS.FARMER_PICKUP(farmerId),
    queryFn: () => pickupApi.options({ farmerId }),
    enabled: Boolean(farmerId),
    staleTime: 60_000,
  });
}
