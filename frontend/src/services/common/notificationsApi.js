import axiosClient from '../../lib/axiosClient';
import { authApi } from './authApi';

/**
 * Notifications, Pass 4B §4.6 (NO-01 → NO-04), mounted at /api/notifications/ and shared by
 * Customer and Farmer. `limit` (1–10) returns the newest rows unpaginated for the N-01 bell.
 */
export const notificationsApi = {
  /** The bell dropdown: the newest rows plus the unread badge, in one round trip each. */
  list: async ({ limit = 10 } = {}) => {
    const [rows, unread] = await Promise.all([
      axiosClient.get('/notifications/', { params: { limit } }),
      axiosClient.get('/notifications/unread-count/'),
    ]);
    return { results: rows.data, unread_count: unread.data.unread_count };
  },

  /** The full page (C-09, F-10), paginated, with an optional read/unread filter. */
  page: async ({ page = 1, isRead } = {}) => {
    const params = { page };
    if (isRead !== undefined) params.is_read = isRead;
    const { data } = await axiosClient.get('/notifications/', { params });
    return data;
  },

  markRead: async (id) => {
    await axiosClient.post(`/notifications/${id}/read/`, {});
  },

  markAllRead: async () => {
    const { data } = await axiosClient.post('/notifications/read-all/', {});
    return data;
  },

  /** AU-08: a ticket is single-use and short-lived, so the socket asks for one per connection. */
  getWsTicket: () => authApi.wsTicket(),
};
