import axiosClient from '../../lib/axiosClient';
import { adaptPaginated } from '../../lib/adapters/pagination.adapter';


export const notificationsApi = {
  list: async ({ page, isRead } = {}, { signal } = {}) => {
    const { data } = await axiosClient.get('/notifications/', {
      params: { page, is_read: isRead },
      signal,
    });
    return adaptPaginated(data);
  },

  
  latest: async (limit, { signal } = {}) => {
    const { data } = await axiosClient.get('/notifications/', { params: { limit }, signal });
    return Array.isArray(data) ? data : [];
  },

  unreadCount: async ({ signal } = {}) => {
    const { data } = await axiosClient.get('/notifications/unread-count/', { signal });
    return data?.unread_count ?? 0;
  },

  markRead: async (id) => {
    const { data } = await axiosClient.post(`/notifications/${id}/read/`);
    return data;
  },

  markAllRead: async () => {
    const { data } = await axiosClient.post('/notifications/read-all/');
    return data;
  },
};
