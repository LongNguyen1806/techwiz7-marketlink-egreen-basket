import axiosClient from '../../lib/axiosClient';
import { adaptPaginated } from '../../lib/adapters/pagination.adapter';




function toRequestBody(payload) {
  if (!Object.values(payload).some((value) => value instanceof File)) return payload;
  const form = new FormData();
  Object.entries(payload).forEach(([key, value]) => {
    if (value === undefined) return;
    if (Array.isArray(value)) value.forEach((item) => form.append(key, String(item)));
    else form.append(key, value instanceof File ? value : value === null ? '' : String(value));
  });
  return form;
}



export const farmerApi = {
  

  
  getOrders: async (params, { signal } = {}) => {
    const { data } = await axiosClient.get('/farmer/orders/', { params, signal });
    return adaptPaginated(data);
  },

  
  // FA-20: per-tab totals plus by_date { 'YYYY-MM-DD': { placed, accepted, ready } } from today on.
  getOrderTabCounts: async ({ marketId } = {}, { signal } = {}) => {
    const { data } = await axiosClient.get('/farmer/orders/tab-counts/', {
      params: { market_id: marketId || undefined },
      signal,
    });
    return data;
  },

  getOrder: async (id, { signal } = {}) => {
    const { data } = await axiosClient.get(`/farmer/orders/${id}/`, { signal });
    return data;
  },

  
  getPickingList: async ({ pickupDate, marketId }, { signal } = {}) => {
    const { data } = await axiosClient.get('/farmer/orders/picking-list/', {
      params: { pickup_date: pickupDate, market_id: marketId || undefined },
      signal,
    });
    return data;
  },

  acceptOrder: async (id, version) => {
    const { data } = await axiosClient.post(`/farmer/orders/${id}/accept/`, {}, { ifMatch: version });
    return data;
  },

  
  declineOrder: async (id, version, { reason, soldOutProductIds = [] }) => {
    const { data } = await axiosClient.post(
      `/farmer/orders/${id}/decline/`,
      { reason, mark_sold_out_product_ids: soldOutProductIds },
      { ifMatch: version },
    );
    return data;
  },

  markOrderReady: async (id, version) => {
    const { data } = await axiosClient.post(`/farmer/orders/${id}/ready/`, {}, { ifMatch: version });
    return data;
  },

  completeOrder: async (id, version) => {
    const { data } = await axiosClient.post(`/farmer/orders/${id}/complete/`, {}, { ifMatch: version });
    return data;
  },

  markOrderNoShow: async (id, version) => {
    const { data } = await axiosClient.post(`/farmer/orders/${id}/no-show/`, {}, { ifMatch: version });
    return data;
  },

  // FA-36: drop one sold-out item from a PLACED order (2+ items) and set its stock to 0 (D-036).
  markOrderItemSoldOut: async (id, version, productId) => {
    const { data } = await axiosClient.post(
      `/farmer/orders/${id}/items/${productId}/mark-sold-out/`,
      {},
      { ifMatch: version },
    );
    return data;
  },

  // FA-37: ACCEPTED / READY orders of one pickup date grouped by customer; not paginated.
  getOrdersByCustomer: async ({ pickupDate, marketId }, { signal } = {}) => {
    const { data } = await axiosClient.get('/farmer/orders/grouped-by-customer/', {
      params: { pickup_date: pickupDate, market_id: marketId || undefined },
      signal,
    });
    return Array.isArray(data) ? data : [];
  },

  // FA-34: apply the shopper's pending change; stock moves by the difference (D-030).
  approveChangeRequest: async (id, version) => {
    const { data } = await axiosClient.post(
      `/farmer/orders/${id}/change-request/approve/`,
      {},
      { ifMatch: version },
    );
    return data;
  },

  // FA-35: drop the pending change and keep the order as it was; reason is optional.
  rejectChangeRequest: async (id, version, { reason } = {}) => {
    const { data } = await axiosClient.post(
      `/farmer/orders/${id}/change-request/reject/`,
      reason ? { reason } : {},
      { ifMatch: version },
    );
    return data;
  },

  

  
  
  getProducts: async (params, { signal } = {}) => {
    const { data } = await axiosClient.get('/farmer/products/', { params, signal });
    return adaptPaginated(data);
  },

  getProduct: async (id, { signal } = {}) => {
    const { data } = await axiosClient.get(`/farmer/products/${id}/`, { signal });
    return data;
  },

  
  createProduct: async (payload) => {
    const { data } = await axiosClient.post('/farmer/products/', toRequestBody(payload));
    return data;
  },

  
  
  updateProduct: async (id, payload) => {
    const { data } = await axiosClient.patch(`/farmer/products/${id}/`, toRequestBody(payload));
    return data;
  },

  markProductSoldOut: async (id) => {
    const { data } = await axiosClient.post(`/farmer/products/${id}/mark-sold-out/`);
    return data;
  },

  
  archiveProduct: async (id) => {
    await axiosClient.delete(`/farmer/products/${id}/`);
  },

  
  
  getWeeklyTemplatePreview: async ({ signal } = {}) => {
    const { data } = await axiosClient.get('/farmer/products/weekly-template-preview/', { signal });
    return data;
  },

  
  applyWeeklyTemplate: async () => {
    const { data } = await axiosClient.post('/farmer/products/apply-weekly-template/');
    return data;
  },

  

  
  
  getDashboard: async ({ from, to } = {}, { signal } = {}) => {
    const { data } = await axiosClient.get('/farmer/dashboard/', { params: { from, to }, signal });
    return data;
  },

  

  
  getProfile: async ({ signal } = {}) => {
    const { data } = await axiosClient.get('/farmer/profile/', { signal });
    return data;
  },

  
  
  
  updateProfile: async (payload) => {
    const { data } = await axiosClient.patch('/farmer/profile/', toRequestBody(payload));
    return data;
  },

  

  
  
  getReviews: async (params, { signal } = {}) => {
    const { data } = await axiosClient.get('/farmer/reviews/', { params, signal });
    return adaptPaginated(data);
  },

  
  replyToReview: async ({ type, id, reply }) => {
    const segment = type === 'PRODUCT' ? 'product-reviews' : 'farmer-reviews';
    const { data } = await axiosClient.post(`/farmer/${segment}/${id}/reply/`, { reply });
    return data;
  },

  

  
  getMarkets: async ({ signal } = {}) => {
    const { data } = await axiosClient.get('/farmer/markets/', { signal });
    return Array.isArray(data) ? data : [];
  },

  joinMarket: async ({ marketId, stallLabel }) => {
    const { data } = await axiosClient.post('/farmer/markets/', { market_id: marketId, stall_label: stallLabel });
    return data;
  },

  updateStallLabel: async (farmerMarketId, stallLabel) => {
    const { data } = await axiosClient.patch(`/farmer/markets/${farmerMarketId}/`, { stall_label: stallLabel });
    return data;
  },

  
  leaveMarket: async (farmerMarketId) => {
    await axiosClient.delete(`/farmer/markets/${farmerMarketId}/`);
  },

  
  createPickupSlot: async ({ farmerMarketId, dayOfWeek, startTime, endTime }) => {
    const { data } = await axiosClient.post('/farmer/pickup-slots/', {
      farmer_market_id: farmerMarketId,
      day_of_week: dayOfWeek,
      start_time: startTime,
      end_time: endTime,
    });
    return data;
  },

  updatePickupSlot: async (slotId, changes) => {
    const { data } = await axiosClient.patch(`/farmer/pickup-slots/${slotId}/`, changes);
    return data;
  },

  // FA-10: RESOURCE_IN_USE (errors.order_ids) while open orders use the slot.
  deletePickupSlot: async (slotId) => {
    await axiosClient.delete(`/farmer/pickup-slots/${slotId}/`);
  },

  // FA-31: current and upcoming time off (D-023).
  getClosures: async ({ signal } = {}) => {
    const { data } = await axiosClient.get('/farmer/closures/', { signal });
    return Array.isArray(data) ? data : [];
  },

  // FA-32: RESOURCE_IN_USE (errors.order_ids) when open orders fall inside the range.
  createClosure: async ({ startDate, endDate, reason }) => {
    const { data } = await axiosClient.post('/farmer/closures/', {
      start_date: startDate,
      end_date: endDate,
      reason: reason || null,
    });
    return data;
  },

  // FA-33.
  deleteClosure: async (closureId) => {
    await axiosClient.delete(`/farmer/closures/${closureId}/`);
  },
};
