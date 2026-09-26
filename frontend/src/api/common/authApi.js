import axiosClient from '../../lib/axiosClient';



export const authApi = {
  login: async (credentials) => {
    const { data } = await axiosClient.post('/auth/login/', credentials);
    return data;
  },

  registerCustomer: async (payload) => {
    const { data } = await axiosClient.post('/auth/register/customer/', payload);
    return data;
  },

  registerFarmer: async (payload) => {
    const { data } = await axiosClient.post('/auth/register/farmer/', payload);
    return data;
  },

  logout: async (refresh) => {
    await axiosClient.post('/auth/logout/', { refresh });
  },

  me: async ({ signal } = {}) => {
    const { data } = await axiosClient.get('/auth/me/', { signal });
    return data;
  },

  changePassword: async (payload) => {
    await axiosClient.post('/auth/change-password/', payload);
  },

  
  wsTicket: async () => {
    const { data } = await axiosClient.post('/auth/ws-ticket/');
    return data;
  },
};
