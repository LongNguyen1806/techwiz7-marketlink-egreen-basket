import { useQuery } from '@tanstack/react-query';
import { announcementsApi } from '../../../services/guest/announcementsApi';
import { QUERY_KEYS } from '../../../constants';


export function useAnnouncements() {
  return useQuery({
    queryKey: QUERY_KEYS.ANNOUNCEMENTS,
    queryFn: announcementsApi.list,
    staleTime: 5 * 60_000,
    retry: false,
  });
}
