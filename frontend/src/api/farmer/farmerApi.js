import axiosClient from '../../lib/axiosClient';
import { adaptPaginated } from '../../lib/adapters/pagination.adapter';

// JSON unless the payload carries a file; then multipart, where null becomes '' (DRF reads
// an empty multipart value as null for nullable fields) and a list is sent as a repeated key
// (operating_days=1&operating_days=3), which is how DRF ListField reads multipart.
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

// Farmer endpoints, all under /api/farmer/. Order actions answer with the full order detail
// and need the order's `version` (sent as If-Match); a stale version gets 409 RESOURCE_MODIFIED.
export const farmerApi = {
  // ---- Orders -------------------------------------------------------------------------

  // params: { tab: placed|accepted|ready|history, q, pickup_from, pickup_to, overdue, page, page_size }
  getOrders: async (params, { signal } = {}) => {
    const { data } = await axiosClient.get('/farmer/orders/', { params, signal });
    return adaptPaginated(data);
  },

  // { placed, accepted, ready, overdue, change_requests }
  getOrderTabCounts: async ({ signal } = {}) => {
    const { data } = await axiosClient.get('/farmer/orders/tab-counts/', { signal });
    return data;
  },

  getOrder: async (id, { signal } = {}) => {
    const { data } = await axiosClient.get(`/farmer/orders/${id}/`, { signal });
    return data;
  },

  // { pickup_date, market_id, rows: [{ product_id, product_name, unit, total_quantity, order_count }] }
  getPickingList: async (pickupDate, { signal } = {}) => {
    const { data } = await axiosClient.get('/farmer/orders/picking-list/', {
      params: { pickup_date: pickupDate },
      signal,
    });
    return data;
  },

  acceptOrder: async (id, version) => {
    const { data } = await axiosClient.post(`/farmer/orders/${id}/accept/`, {}, { ifMatch: version });
    return data;
  },

  // Declining an accepted order must say which items are sold out; [] returns all to stock.
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

  // ---- Products -----------------------------------------------------------------------

  // params: { q, state: in_stock|out_of_stock|unavailable|hidden|archived, category_id, page, page_size }
  // Without `state` the backend leaves archived products out.
  getProducts: async (params, { signal } = {}) => {
    const { data } = await axiosClient.get('/farmer/products/', { params, signal });
    return adaptPaginated(data);
  },

  getProduct: async (id, { signal } = {}) => {
    const { data } = await axiosClient.get(`/farmer/products/${id}/`, { signal });
    return data;
  },

  // payload.image is a File (JPG/PNG/WEBP, max 2 MB); the server re-encodes it.
  createProduct: async (payload) => {
    const { data } = await axiosClient.post('/farmer/products/', toRequestBody(payload));
    return data;
  },

  // Partial update: send only the fields that changed. Answers with the product plus
  // `restock_notified`, the number of shoppers told it is back in stock.
  updateProduct: async (id, payload) => {
    const { data } = await axiosClient.patch(`/farmer/products/${id}/`, toRequestBody(payload));
    return data;
  },

  markProductSoldOut: async (id) => {
    const { data } = await axiosClient.post(`/farmer/products/${id}/mark-sold-out/`);
    return data;
  },

  // Soft delete: the product is archived, not removed.
  archiveProduct: async (id) => {
    await axiosClient.delete(`/farmer/products/${id}/`);
  },

  // { rows: [{ product_id, name, weekly_default_quantity, held_quantity, pending_quantity,
  //   current_stock, new_stock, is_available }], overdue_orders: OrderSummary[] }
  getWeeklyTemplatePreview: async ({ signal } = {}) => {
    const { data } = await axiosClient.get('/farmer/products/weekly-template-preview/', { signal });
    return data;
  },

  // { updated_count, restock_notified }
  applyWeeklyTemplate: async () => {
    const { data } = await axiosClient.post('/farmer/products/apply-weekly-template/');
    return data;
  },

  // ---- Dashboard ------------------------------------------------------------------------

  // { from, to } as YYYY-MM-DD (at most 366 days). Answers { kpis, revenue_by_day, top_products,
  // overdue_open_count, upcoming, status, status_reason, range }. Money values are strings.
  getDashboard: async ({ from, to } = {}, { signal } = {}) => {
    const { data } = await axiosClient.get('/farmer/dashboard/', { params: { from, to }, signal });
    return data;
  },

  // ---- Profile --------------------------------------------------------------------------

  // FarmerPublic + { email, status, status_reason, location_found, operating_days, order_cutoff_hours, ... }
  getProfile: async ({ signal } = {}) => {
    const { data } = await axiosClient.get('/farmer/profile/', { signal });
    return data;
  },

  // Partial update; multipart when a new image is sent. Removing an operating day that
  // open orders still use is refused with RESOURCE_IN_USE (errors.order_ids); otherwise the
  // answer may carry deactivated_slot_count, the pickup slots switched off on removed days.
  updateProfile: async (payload) => {
    const { data } = await axiosClient.patch('/farmer/profile/', toRequestBody(payload));
    return data;
  },

  // ---- Reviews ----------------------------------------------------------------------------

  // params: { type: FARMER|PRODUCT, rating: 1-5, replied: true|false, page, page_size }.
  // Stall and product reviews share one list, newest first; their ids may overlap.
  getReviews: async (params, { signal } = {}) => {
    const { data } = await axiosClient.get('/farmer/reviews/', { params, signal });
    return adaptPaginated(data);
  },

  // Each review type has its own reply endpoint. Answers with the updated review.
  replyToReview: async ({ type, id, reply }) => {
    const segment = type === 'PRODUCT' ? 'product-reviews' : 'farmer-reviews';
    const { data } = await axiosClient.post(`/farmer/${segment}/${id}/reply/`, { reply });
    return data;
  },

  // ---- Markets and pickup slots -----------------------------------------------------------

  // [{ id, market: MarketSummary, is_market_active, stall_label, slots, open_order_count }]
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

  // Refused with RESOURCE_IN_USE while open orders exist at the market.
  leaveMarket: async (farmerMarketId) => {
    await axiosClient.delete(`/farmer/markets/${farmerMarketId}/`);
  },

  // Times are "HH:mm". Answers with the slot { id, day_of_week, start_time, end_time, is_active }.
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
};
