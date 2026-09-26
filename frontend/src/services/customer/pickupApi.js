import axiosClient from '../../lib/axiosClient';


export const pickupApi = {
  options: async ({ farmerId, from, days } = {}) => {
    const params = {};
    if (from) params.from = from;
    if (days) params.days = days;
    const { data } = await axiosClient.get(`/public/farmers/${farmerId}/pickup-options/`, { params });
    return data;
  },
};
