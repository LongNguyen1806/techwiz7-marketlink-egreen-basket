import { useQuery } from '@tanstack/react-query';
import { announcementsApi } from '../../../services/guest/announcementsApi';
import { QUERY_KEYS } from '../../../constants';

/**
 * PU-13 for the banner. It is decoration on top of every page, so a failure here must never take the
 * page with it: the query simply returns nothing and the banner renders nothing.
 */
export function useAnnouncements() {
  return useQuery({
    queryKey: QUERY_KEYS.ANNOUNCEMENTS,
    queryFn: announcementsApi.list,
    staleTime: 5 * 60_000,
    retry: false,
  });
}
