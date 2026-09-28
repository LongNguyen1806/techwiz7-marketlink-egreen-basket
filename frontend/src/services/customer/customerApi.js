import axiosClient from '../../lib/axiosClient';

function toRequestBody(payload) {
  if (!(payload.image instanceof File)) return payload;
  const form = new FormData();
  Object.entries(payload).forEach(([key, value]) => form.append(key, value));
  return form;
}


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
    const { data } = await axiosClient.patch('/customer/profile/', toRequestBody(payload));
    return data;
  },
};
