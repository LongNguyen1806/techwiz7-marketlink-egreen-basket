import { useMemo } from 'react';
import { keepPreviousData, useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { farmerApi } from '../../../api/farmer/farmerApi';
import { farmerKeys } from '../../../constants/queryKeys';
import { STALE } from '../../../constants/staleTimes';

export const ORDERS_PAGE_SIZE = 20;


const flattenPages = (data) => ({
  orders: data.pages.flatMap((page) => page.results),
  total: data.pages[0]?.count ?? 0,
});

const byPickupEnd = (a, b) => new Date(a.pickup_end_at) - new Date(b.pickup_end_at);


export function useFarmerOrderList(filters, { enabled = true } = {}) {
  return useInfiniteQuery({
    queryKey: farmerKeys.orders.list(filters),
    queryFn: ({ pageParam, signal }) =>
      farmerApi.getOrders({ ...filters, page: pageParam, page_size: ORDERS_PAGE_SIZE }, { signal }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => lastPage.next ?? undefined,
    select: flattenPages,
    placeholderData: keepPreviousData,
    staleTime: STALE.SEARCH,
    enabled,
  });
}


export function useFarmerOverdueOrders(filters, { enabled = true } = {}) {
  const accepted = useFarmerOrderList({ ...filters, tab: 'accepted', overdue: true }, { enabled });
  const ready = useFarmerOrderList({ ...filters, tab: 'ready', overdue: true }, { enabled });
  const parts = [accepted, ready];

  const orders = useMemo(
    () => [...(accepted.data?.orders ?? []), ...(ready.data?.orders ?? [])].sort(byPickupEnd),
    [accepted.data, ready.data],
  );

  return {
    data: { orders, total: (accepted.data?.total ?? 0) + (ready.data?.total ?? 0) },
    isPending: parts.some((q) => q.isPending),
    isError: parts.some((q) => q.isError),
    isFetching: parts.some((q) => q.isFetching),
    isPlaceholderData: parts.some((q) => q.isPlaceholderData),
    hasNextPage: parts.some((q) => q.hasNextPage),
    isFetchingNextPage: parts.some((q) => q.isFetchingNextPage),
    fetchNextPage: () => parts.forEach((q) => q.hasNextPage && q.fetchNextPage()),
    refetch: () => parts.forEach((q) => q.refetch()),
  };
}

export function useFarmerOrderTabCounts() {
  return useQuery({
    queryKey: farmerKeys.orders.tabCounts(),
    queryFn: ({ signal }) => farmerApi.getOrderTabCounts({ signal }),
    staleTime: STALE.LIVE,
  });
}


export function useFarmerOrder(id, { enabled = true } = {}) {
  const orderId = Number(id);
  return useQuery({
    queryKey: farmerKeys.orders.detail(orderId),
    queryFn: ({ signal }) => farmerApi.getOrder(orderId, { signal }),
    staleTime: STALE.LIVE,
    enabled: enabled && Number.isInteger(orderId) && orderId > 0,
  });
}

const pickingRows = (data) => data.rows ?? [];

export function usePickingList(pickupDate, { enabled = true } = {}) {
  return useQuery({
    queryKey: farmerKeys.orders.pickingList(pickupDate),
    queryFn: ({ signal }) => farmerApi.getPickingList(pickupDate, { signal }),
    select: pickingRows,
    staleTime: STALE.SHORT,
    placeholderData: keepPreviousData,
    enabled: enabled && Boolean(pickupDate),
  });
}
