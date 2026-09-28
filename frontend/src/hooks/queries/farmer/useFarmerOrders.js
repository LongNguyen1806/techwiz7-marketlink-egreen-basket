import { useMemo } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { farmerApi } from '../../../api/farmer/farmerApi';
import { farmerKeys } from '../../../constants/queryKeys';
import { STALE } from '../../../constants/staleTimes';

export const ORDERS_PAGE_SIZE = 20;


const toPage = (data) => ({
  orders: data.results,
  total: data.count,
  page: data.page,
  pageSize: data.page_size,
  totalPages: data.total_pages,
});

const byPickupEnd = (a, b) => new Date(a.pickup_end_at) - new Date(b.pickup_end_at);


export function useFarmerOrderList(filters, { enabled = true } = {}) {
  return useQuery({
    queryKey: farmerKeys.orders.list(filters),
    queryFn: ({ signal }) =>
      farmerApi.getOrders({ ...filters, page: filters.page ?? 1, page_size: ORDERS_PAGE_SIZE }, { signal }),
    select: toPage,
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
    data: {
      orders,
      total: (accepted.data?.total ?? 0) + (ready.data?.total ?? 0),
      page: filters.page ?? 1,
      pageSize: ORDERS_PAGE_SIZE * 2,
      totalPages: Math.max(accepted.data?.totalPages ?? 0, ready.data?.totalPages ?? 0),
    },
    isPending: parts.some((q) => q.isPending),
    isError: parts.some((q) => q.isError),
    isFetching: parts.some((q) => q.isFetching),
    isPlaceholderData: parts.some((q) => q.isPlaceholderData),
    refetch: () => parts.forEach((q) => q.refetch()),
  };
}

export function useFarmerOrderTabCounts({ marketId = 0 } = {}) {
  return useQuery({
    queryKey: farmerKeys.orders.tabCounts(marketId),
    queryFn: ({ signal }) => farmerApi.getOrderTabCounts({ marketId }, { signal }),
    placeholderData: keepPreviousData,
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

export function useOrdersByCustomer(pickupDate, { marketId = 0, enabled = true } = {}) {
  return useQuery({
    queryKey: farmerKeys.orders.byCustomer(pickupDate, marketId),
    queryFn: ({ signal }) => farmerApi.getOrdersByCustomer({ pickupDate, marketId }, { signal }),
    staleTime: STALE.SHORT,
    placeholderData: keepPreviousData,
    enabled: enabled && Boolean(pickupDate),
  });
}

const pickingRows = (data) => data.rows ?? [];

export function usePickingList(pickupDate, { marketId = 0, enabled = true } = {}) {
  return useQuery({
    queryKey: farmerKeys.orders.pickingList(pickupDate, marketId),
    queryFn: ({ signal }) => farmerApi.getPickingList({ pickupDate, marketId }, { signal }),
    select: pickingRows,
    staleTime: STALE.SHORT,
    placeholderData: keepPreviousData,
    enabled: enabled && Boolean(pickupDate),
  });
}
