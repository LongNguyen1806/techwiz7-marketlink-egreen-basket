import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { notificationsApi } from '../../../services/common/notificationsApi';
import { ApiError } from '../../../lib/ApiError';
import { QUERY_KEYS } from '../../../constants';


export function useNotificationFeed({ page, isRead }) {
  const queryClient = useQueryClient();
  const params = { page, ...(isRead === undefined ? {} : { isRead }) };

  const query = useQuery({
    queryKey: QUERY_KEYS.NOTIFICATIONS_PAGE(params),
    queryFn: () => notificationsApi.page(params),
  });

  function refresh() {
    
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
