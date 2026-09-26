import axiosClient from '../../lib/axiosClient';
import { adaptMe } from '../../lib/adapters/auth.adapter';


function adaptLogin(raw) {
  return {
    access: raw.access,
    refresh: raw.refresh,
    user: adaptMe(raw.user),
  };
}

export const authApi = {
  
  login: async (payload) => {
    const { data } = await axiosClient.post('/auth/login/', payload);
    return adaptLogin(data);
  },

  
  adminLogin: async (payload) => {
    const { data } = await axiosClient.post('/auth/admin/login/', payload);
    return adaptLogin(data);
  },

  
  logout: async ({ refresh }) => {
    await axiosClient.post('/auth/logout/', { refresh });
  },

  
  refresh: async (refresh) => {
    const { data } = await axiosClient.post('/auth/refresh/', { refresh });
    return data;
  },

  
  me: async () => {
    const { data } = await axiosClient.get('/auth/me/');
    return adaptMe(data);
  },

  
  changePassword: async (payload) => {
    await axiosClient.post('/auth/change-password/', payload);
  },

  
  wsTicket: async () => {
    const { data } = await axiosClient.post('/auth/ws-ticket/', {});
    return data;
  },

  
  registerCustomer: async (payload) => {
    const { data } = await axiosClient.post('/auth/register/customer/', payload);
    return adaptLogin(data);
  },

  
  registerFarmer: async (payload) => {
    const { data } = await axiosClient.post('/auth/register/farmer/', payload);
    return adaptLogin(data);
  },
};
