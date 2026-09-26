import axiosClient from '../../lib/axiosClient';
import { adaptPaginated } from '../../lib/adapters/pagination.adapter';

// Public endpoints (no sign-in needed), all under /api/public/.
export const catalogApi = {
  // { ai_chat_enabled, booking_horizon_days, max_placed_orders_per_customer, max_upload_mb, ... }
  getConfig: async ({ signal } = {}) => {
    const { data } = await axiosClient.get('/public/config/', { signal });
    return data;
  },

  // [{ id, name, icon, display_order }]
  getCategories: async ({ signal } = {}) => {
    const { data } = await axiosClient.get('/public/categories/', { signal });
    return Array.isArray(data) ? data : [];
  },

  getMarkets: async (params = {}, { signal } = {}) => {
    const { data } = await axiosClient.get('/public/markets/', { params, signal });
    return adaptPaginated(data);
  },
};
