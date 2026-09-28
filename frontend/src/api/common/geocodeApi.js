import axiosClient from '../../lib/axiosClient';

export const geocodeApi = {
  lookup: async (q) => {
    const { data } = await axiosClient.get('/public/geocode/', { params: { q } });
    return data;
  },
};
