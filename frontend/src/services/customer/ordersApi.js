import axiosClient from '../../lib/axiosClient';

/** Customer orders, Pass 4B §4.2. */
export const ordersApi = {
  /**
   * CU-04 (C-02): one request creates one independent order per farmer, all or nothing (D-004).
   * `idempotent` makes the client send an `Idempotency-Key`, which the endpoint requires — a retry
   * of the same attempt replays the first answer instead of ordering twice.
   */
  checkout: async ({ groups }) => {
    const { data } = await axiosClient.post('/customer/orders/', { groups }, { idempotent: true });
    return data;
  },

  /** CU-05 (C-04). Paginated. `status` is a comma-separated list, `tab` is `open` or `history`. */
  list: async (params = {}) => {
    const { data } = await axiosClient.get('/customer/orders/', { params });
    return data;
  },

  /** CU-06 (C-05, C-06, C-07). Carries `allowed_actions`, so the screen renders no button of its own. */
  detail: async (orderId) => {
    const { data } = await axiosClient.get(`/customer/orders/${orderId}/`);
    return data;
  },

  /**
   * CU-07 (C-06). `items` is the complete list after the edit, not a difference, and a reschedule
   * needs `pickup_slot_id` and `pickup_date` together. A PLACED order changes at once; an ACCEPTED one
   * records a change request and keeps its current contents until the farmer decides (D-030).
   *
   * `If-Match` carries the version the screen was showing: a second tab that edited first turns this
   * into 409 RESOURCE_MODIFIED instead of silently overwriting.
   */
  modify: async ({ orderId, version, body }) => {
    const { data } = await axiosClient.patch(`/customer/orders/${orderId}/`, body, { ifMatch: String(version) });
    return data;
  },

  /** CU-08 (C-05): T5 from PLACED, T6 from ACCEPTED, both only before the cut-off. */
  cancel: async ({ orderId, version, reason }) => {
    const body = reason ? { reason } : {};
    const { data } = await axiosClient.post(`/customer/orders/${orderId}/cancel/`, body, { ifMatch: String(version) });
    return data;
  },

  /** CU-09 (C-04, C-05): read-only, at today's prices, with whatever can no longer be ordered listed apart. */
  reorderPreview: async (orderId) => {
    const { data } = await axiosClient.get(`/customer/orders/${orderId}/reorder-preview/`);
    return data;
  },
};
