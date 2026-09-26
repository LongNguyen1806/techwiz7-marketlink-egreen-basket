import { useQuery } from '@tanstack/react-query';
import { pickupApi } from '../../../services/customer/pickupApi';
import { QUERY_KEYS } from '../../../constants';


export function usePickupOptions(farmerId) {
  return useQuery({
    queryKey: QUERY_KEYS.FARMER_PICKUP(farmerId),
    queryFn: () => pickupApi.options({ farmerId }),
    enabled: Boolean(farmerId),
    staleTime: 60_000,
  });
}
