import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { notificationsApi } from '../../../services/common/notificationsApi';
import { ApiError } from '../../../lib/ApiError';
import { QUERY_KEYS } from '../../../constants';

/**
 * The full notification list behind C-09 and F-10 (NO-01, NO-03, NO-04).
 *
 * The unread filter is `is_read=false` on the server rather than a sieve in the browser: the list is
 * paginated, so filtering what one page happens to hold would quietly lose rows.
 */
export function useNotificationFeed({ page, isRead }) {
  const queryClient = useQueryClient();
  const params = { page, ...(isRead === undefined ? {} : { isRead }) };

  const query = useQuery({
    queryKey: QUERY_KEYS.NOTIFICATIONS_PAGE(params),
    queryFn: () => notificationsApi.page(params),
  });

  function refresh() {
    // The bell shares the same rows and the same badge, so both are invalidated together.
    queryClient.invalidateQueries({ queryKey: ['notifications-page'] });
    queryClient.invalidateQueries({ queryKey: QUERY_KEYS.NOTIFICATIONS_LIST });
  }

  const markOne = useMutation({
    mutationFn: notificationsApi.markRead,
    onSuccess: refresh,
    onError: (error) => toast.error(ApiError.fromUnknown(error).friendlyMessage),
  });

  const markAll = useMutation({
    mutationFn: notificationsApi.markAllRead,
    onSuccess: () => {
      toast.success('All notifications marked as read');
      refresh();
    },
    onError: (error) => toast.error(ApiError.fromUnknown(error).friendlyMessage),
  });

  return { query, markOne, markAll };
}
