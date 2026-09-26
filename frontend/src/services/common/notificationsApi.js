import axiosClient from '../../lib/axiosClient';
import { authApi } from './authApi';


export const notificationsApi = {
  
  list: async ({ limit = 10 } = {}) => {
    const [rows, unread] = await Promise.all([
      axiosClient.get('/notifications/', { params: { limit } }),
      axiosClient.get('/notifications/unread-count/'),
    ]);
    return { results: rows.data, unread_count: unread.data.unread_count };
  },

  
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

  
  getWsTicket: () => authApi.wsTicket(),
};
