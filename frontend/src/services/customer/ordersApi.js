import axiosClient from '../../lib/axiosClient';


export const ordersApi = {
  
  checkout: async ({ groups }) => {
    const { data } = await axiosClient.post('/customer/orders/', { groups }, { idempotent: true });
    return data;
  },

  
  list: async (params = {}) => {
    const { data } = await axiosClient.get('/customer/orders/', { params });
    return data;
  },

  
  detail: async (orderId) => {
    const { data } = await axiosClient.get(`/customer/orders/${orderId}/`);
    return data;
  },

  
  modify: async ({ orderId, version, body }) => {
    const { data } = await axiosClient.patch(`/customer/orders/${orderId}/`, body, { ifMatch: String(version) });
    return data;
  },

  
  cancel: async ({ orderId, version, reason }) => {
    const body = reason ? { reason } : {};
    const { data } = await axiosClient.post(`/customer/orders/${orderId}/cancel/`, body, { ifMatch: String(version) });
    return data;
  },

  
  reorderPreview: async (orderId) => {
    const { data } = await axiosClient.get(`/customer/orders/${orderId}/reorder-preview/`);
    return data;
  },
};
