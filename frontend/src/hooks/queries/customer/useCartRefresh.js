import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { catalogApi, MAX_IDS } from '../../../services/guest/catalogApi';
import { QUERY_KEYS } from '../../../constants';
import { useCartStore } from '../../../stores/cart.store';

/**
 * C-01 opens with prices and stock that may be days old, so every line is read back from PU-10 and
 * written into the store. Stale money is the reason: the cart shows a price, CU-04 charges the one in
 * the database, and the customer should see the difference before confirming, not after.
 */
export function useCartRefresh() {
  const lines = useCartStore((state) => state.lines);
  const refreshLines = useCartStore((state) => state.refreshLines);
  const ids = lines.map((line) => line.product_id).slice(0, MAX_IDS).sort((a, b) => a - b);

  const query = useQuery({
    queryKey: QUERY_KEYS.PRODUCTS({ ids: ids.join(',') }),
    queryFn: () => catalogApi.products({ ids }),
    enabled: ids.length > 0,
    staleTime: 0,
  });

  useEffect(() => {
    if (query.data?.results) refreshLines(query.data.results);
  }, [query.data, refreshLines]);

  return { isRefreshing: query.isFetching, error: query.error };
}
