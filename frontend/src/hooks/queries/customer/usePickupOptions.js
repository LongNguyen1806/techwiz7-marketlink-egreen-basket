import { useQuery } from '@tanstack/react-query';
import { pickupApi } from '../../../services/customer/pickupApi';
import { QUERY_KEYS } from '../../../constants';


export function usePickupOptions(farmerId, productIds = []) {
  const products = [...new Set(productIds)].sort((a, b) => a - b);
  return useQuery({
    queryKey: [...QUERY_KEYS.FARMER_PICKUP(farmerId), products.join(',')],
    queryFn: () => pickupApi.options({ farmerId, productIds: products }),
    enabled: Boolean(farmerId),
    staleTime: 60_000,
  });
}
