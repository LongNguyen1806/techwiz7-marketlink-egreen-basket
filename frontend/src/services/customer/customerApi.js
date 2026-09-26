import axiosClient from '../../lib/axiosClient';


export const customerApi = {
  
  dashboard: async () => {
    const { data } = await axiosClient.get('/customer/dashboard/');
    return data;
  },

  
  profile: async () => {
    const { data } = await axiosClient.get('/customer/profile/');
    return data;
  },

  
  updateProfile: async (payload) => {
    const { data } = await axiosClient.patch('/customer/profile/', payload);
    return data;
  },
};
