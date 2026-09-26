import axiosClient from '../../lib/axiosClient';

/**
 * Reviews a customer writes (CU-10, CU-11 — C-07). Only a COMPLETED order can be reviewed, and each
 * subject once: a second attempt comes back 422 REVIEW_NOT_ALLOWED.
 */
export const reviewsApi = {
  /** CU-10: the stall as a whole. */
  farmer: async ({ orderId, rating, comment }) => {
    const { data } = await axiosClient.post(`/customer/orders/${orderId}/farmer-review/`, { rating, comment });
    return data;
  },

  /** CU-11: one line of the order, addressed by its order item id. */
  item: async ({ orderId, itemId, rating, comment }) => {
    const { data } = await axiosClient.post(
      `/customer/orders/${orderId}/items/${itemId}/review/`,
      { rating, comment },
    );
    return data;
  },
};
