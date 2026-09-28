import axiosClient from '../../lib/axiosClient';


export const pickupApi = {
  options: async ({ farmerId, from, days, productIds } = {}) => {
    const params = {};
    if (from) params.from = from;
    if (days) params.days = days;
    if (productIds?.length) params.products = productIds.join(',');
    const { data } = await axiosClient.get(`/public/farmers/${farmerId}/pickup-options/`, { params });
    return data;
  },
};
