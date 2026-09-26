import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { notificationsApi } from '../../../api/common/notificationsApi';
import { notificationKeys } from '../../../constants/queryKeys';
import { NOTIFICATION_POLL_INTERVAL, STALE } from '../../../constants/staleTimes';
import { useUiStore } from '../../../stores/ui.store';

export const BELL_LIMIT = 5;

// The WebSocket pushes new notifications; polling only runs while it is disconnected.
function usePollInterval() {
  const connected = useUiStore((state) => state.realtimeConnected);
  return connected ? false : NOTIFICATION_POLL_INTERVAL;
}

export function useUnreadNotificationCount() {
  const refetchInterval = usePollInterval();
  return useQuery({
    queryKey: notificationKeys.unreadCount(),
    queryFn: ({ signal }) => notificationsApi.unreadCount({ signal }),
    staleTime: STALE.SHORT,
    refetchInterval,
  });
}

export function useLatestNotifications(limit = BELL_LIMIT) {
  const refetchInterval = usePollInterval();
  return useQuery({
    queryKey: notificationKeys.latest(limit),
    queryFn: ({ signal }) => notificationsApi.latest(limit, { signal }),
    staleTime: STALE.SHORT,
    refetchInterval,
  });
}

export function useNotificationList({ page = 1, isRead } = {}) {
  const params = { page, isRead };
  return useQuery({
    queryKey: notificationKeys.list(params),
    queryFn: ({ signal }) => notificationsApi.list(params, { signal }),
    staleTime: STALE.SHORT,
    placeholderData: keepPreviousData,
  });
}

// Notification caches hold either an array (bell) or a page { results }; the unread count
// is a number and passes through untouched.
function patchItems(data, patch) {
  if (Array.isArray(data)) return data.map(patch);
  if (data && Array.isArray(data.results)) return { ...data, results: data.results.map(patch) };
  return data;
}

function findItem(data, id) {
  const items = Array.isArray(data) ? data : data?.results;
  return Array.isArray(items) ? items.find((item) => item.id === id) : undefined;
}

// Optimistic update shared by "mark one" and "mark all": apply now, roll back on error,
// then refetch so counts match the server.
function useOptimisticRead({ mutationFn, markItem, nextUnread }) {
  const queryClient = useQueryClient();
  const filters = { queryKey: notificationKeys.all() };

  return useMutation({
    mutationFn,
    onMutate: async (variables) => {
      await queryClient.cancelQueries(filters);
      const snapshot = queryClient.getQueriesData(filters);
      const readAt = new Date().toISOString();

      queryClient.setQueriesData(filters, (data) =>
        patchItems(data, (item) => (markItem(item, variables) ? { ...item, is_read: true, read_at: readAt } : item)),
      );
      queryClient.setQueryData(notificationKeys.unreadCount(), (count) =>
        count === undefined ? count : nextUnread(count, variables, snapshot),
      );
      return { snapshot };
    },
    onError: (_error, _variables, context) => {
      context?.snapshot.forEach(([key, data]) => queryClient.setQueryData(key, data));
    },
    onSettled: () => queryClient.invalidateQueries(filters),
  });
}

export function useMarkNotificationRead() {
  return useOptimisticRead({
    mutationFn: notificationsApi.markRead,
    markItem: (item, id) => item.id === id,
    nextUnread: (count, id, snapshot) => {
      const wasUnread = snapshot.some(([, data]) => findItem(data, id)?.is_read === false);
      return wasUnread ? Math.max(0, count - 1) : count;
    },
  });
}

export function useMarkAllNotificationsRead() {
  return useOptimisticRead({
    mutationFn: notificationsApi.markAllRead,
    markItem: () => true,
    nextUnread: () => 0,
  });
}
