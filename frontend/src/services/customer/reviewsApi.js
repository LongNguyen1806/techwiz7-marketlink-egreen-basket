import axiosClient from '../../lib/axiosClient';


export const reviewsApi = {
  
  farmer: async ({ orderId, rating, comment }) => {
    const { data } = await axiosClient.post(`/customer/orders/${orderId}/farmer-review/`, { rating, comment });
    return data;
  },

  
  item: async ({ orderId, itemId, rating, comment }) => {
    const { data } = await axiosClient.post(
      `/customer/orders/${orderId}/items/${itemId}/review/`,
      { rating, comment },
    );
    return data;
  },
};
