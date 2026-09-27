import axiosClient from '@/lib/axiosClient';
import { adaptPaginated } from '@/lib/adapters/pagination.adapter';

/** /api/admin/* is the intentional DRF admin branch (see BE urls comment). */
// AD-23 and AD-24 are separate endpoints because farmer_reviews.id and
// product_reviews.id are different id spaces - the same number means two reviews.
function reviewSegment(type) {
  return type === 'FARMER' ? 'farmer-reviews' : 'product-reviews';
}

export const adminApi = {
  getDashboard: async () => {
    const { data } = await axiosClient.get('/admin/dashboard/');
    return data;
  },

  getFarmers: async (params = {}) => {
    const { data } = await axiosClient.get('/admin/farmers/', { params });
    return adaptPaginated(data);
  },

  getFarmer: async (id) => {
    const { data } = await axiosClient.get(`/admin/farmers/${id}/`);
    return data;
  },

  // One calendar month of the orders chart. Its own call, not part of the dashboard, so
  // stepping through months does not refetch the totals and the queue on every click.
  getOrdersByMonth: async (month) => {
    const { data } = await axiosClient.get('/admin/dashboard/orders-by-day/', {
      params: month ? { month } : undefined,
    });
    return data;
  },

  getFarmerImpact: async (id) => {
    const { data } = await axiosClient.get(`/admin/farmers/${id}/suspension-impact/`);
    return data;
  },

  approveFarmer: async (id) => {
    const { data } = await axiosClient.post(`/admin/farmers/${id}/approve/`);
    return data;
  },

  rejectFarmer: async (id, reason) => {
    const { data } = await axiosClient.post(`/admin/farmers/${id}/reject/`, { reason });
    return data;
  },

  suspendFarmer: async (id, reason) => {
    const { data } = await axiosClient.post(`/admin/farmers/${id}/suspend/`, { reason });
    return data;
  },

  reinstateFarmer: async (id) => {
    const { data } = await axiosClient.post(`/admin/farmers/${id}/reinstate/`);
    return data;
  },

  getCustomers: async (params = {}) => {
    const { data } = await axiosClient.get('/admin/customers/', { params });
    return adaptPaginated(data);
  },

  // AD-03 PATCH. Contact details only: operating days and coordinates carry rules that live
  // on the stall's own profile screen (D-031, D-032).
  updateFarmer: async (id, payload) => {
    const { data } = await axiosClient.patch(`/admin/farmers/${id}/`, payload);
    return data;
  },

  // AD-10 PATCH.
  updateCustomer: async (id, payload) => {
    const { data } = await axiosClient.patch(`/admin/customers/${id}/`, payload);
    return data;
  },

  getCustomer: async (id) => {
    const { data } = await axiosClient.get(`/admin/customers/${id}/`);
    return data;
  },

  getCustomerImpact: async (id) => {
    const { data } = await axiosClient.get(`/admin/customers/${id}/deactivation-impact/`);
    return data;
  },

  deactivateCustomer: async (id, reason) => {
    const { data } = await axiosClient.post(`/admin/customers/${id}/deactivate/`, {
      reason,
    });
    return data;
  },

  activateCustomer: async (id) => {
    const { data } = await axiosClient.post(`/admin/customers/${id}/activate/`);
    return data;
  },

  getMarkets: async (params = {}) => {
    const { data } = await axiosClient.get('/admin/markets/', { params });
    return adaptPaginated(data);
  },

  getMarket: async (id) => {
    const { data } = await axiosClient.get(`/admin/markets/${id}/`);
    return data;
  },

  createMarket: async (payload) => {
    const { data } = await axiosClient.post('/admin/markets/', payload);
    return data;
  },

  updateMarket: async (id, payload) => {
    const { data } = await axiosClient.patch(`/admin/markets/${id}/`, payload);
    return data;
  },

  activateMarket: async (id) => {
    const { data } = await axiosClient.post(`/admin/markets/${id}/activate/`);
    return data;
  },

  // AD-17. Closing carries out the orders still open at the market, so the reason the admin
  // gives is what both the shoppers and the stalls are told.
  deactivateMarket: async (id, reason, farmerMessage = '') => {
    const { data } = await axiosClient.post(`/admin/markets/${id}/deactivate/`, {
      reason,
      farmer_message: farmerMessage,
    });
    return data;
  },

  // AD-31: a plain array, not a paginated page.
  getMarketClosures: async (marketId, includePast = false) => {
    const { data } = await axiosClient.get(`/admin/markets/${marketId}/closures/`, {
      params: includePast ? { include_past: true } : undefined,
    });
    return data;
  },

  createMarketClosure: async (marketId, payload) => {
    const { data } = await axiosClient.post(
      `/admin/markets/${marketId}/closures/`,
      payload,
    );
    return data;
  },

  deleteMarketClosure: async (closureId) => {
    await axiosClient.delete(`/admin/market-closures/${closureId}/`);
  },

  getCategories: async () => {
    const { data } = await axiosClient.get('/admin/categories/');
    return data;
  },

  createCategory: async (payload) => {
    const { data } = await axiosClient.post('/admin/categories/', payload);
    return data;
  },

  updateCategory: async (id, payload) => {
    const { data } = await axiosClient.patch(`/admin/categories/${id}/`, payload);
    return data;
  },

  // There is no bulk reorder endpoint: A-07 edits display_order through AD-19, one
  // category at a time. The list is short, so the writes go out together.
  reorderCategories: async (ordered_ids) => {
    return Promise.all(
      ordered_ids.map(async (id, index) => {
        const { data } = await axiosClient.patch(`/admin/categories/${id}/`, {
          display_order: index + 1,
        });
        return data;
      }),
    );
  },

  deleteCategory: async (id) => {
    await axiosClient.delete(`/admin/categories/${id}/`);
  },

  getModerationProducts: async (params = {}) => {
    const { data } = await axiosClient.get('/admin/products/', { params });
    return adaptPaginated(data);
  },

  hideProduct: async (id, reason) => {
    const { data } = await axiosClient.post(`/admin/products/${id}/hide/`, { reason });
    return data;
  },

  restoreProduct: async (id) => {
    const { data } = await axiosClient.post(`/admin/products/${id}/restore/`);
    return data;
  },

  // A listing is written by a stall and shown to shoppers by an admin. Approving is one
  // click; refusing has to say why, because the stall can only fix what it is told about.
  approveProduct: async (id) => {
    const { data } = await axiosClient.post(`/admin/products/${id}/approve/`);
    return data;
  },

  rejectProduct: async (id, reason) => {
    const { data } = await axiosClient.post(`/admin/products/${id}/reject/`, { reason });
    return data;
  },

  // AD-21b. A takedown, unlike a hide, also cancels the open orders, so the dialog asks what
  // that would cost before the admin commits to it.
  fetchProductBlockImpact: async (id) => {
    const { data } = await axiosClient.get(`/admin/products/${id}/block-impact/`);
    return data;
  },

  blockProduct: async (id, reason) => {
    const { data } = await axiosClient.post(`/admin/products/${id}/block/`, { reason });
    return data;
  },

  unblockProduct: async (id) => {
    const { data } = await axiosClient.post(`/admin/products/${id}/unblock/`);
    return data;
  },

  getModerationReviews: async (params = {}) => {
    const { data } = await axiosClient.get('/admin/reviews/', { params });
    return adaptPaginated(data);
  },

  hideReview: async (id, type, reason) => {
    const { data } = await axiosClient.post(`/admin/${reviewSegment(type)}/${id}/hide/`, {
      reason,
    });
    return data;
  },

  restoreReview: async (id, type) => {
    const { data } = await axiosClient.post(
      `/admin/${reviewSegment(type)}/${id}/restore/`,
    );
    return data;
  },

  getReports: async (params) => {
    const { data } = await axiosClient.get('/admin/reports/summary/', {
      params,
    });
    return data;
  },

  exportReports: async (params) => {
    const response = await axiosClient.get('/admin/reports/export/', {
      params,
      responseType: 'blob',
    });
    return response.data;
  },

  getAnnouncements: async (params = {}) => {
    const { data } = await axiosClient.get('/admin/announcements/', { params });
    return adaptPaginated(data);
  },

  createAnnouncement: async (payload) => {
    const { data } = await axiosClient.post('/admin/announcements/', payload);
    return data;
  },

  updateAnnouncement: async (id, payload) => {
    const { data } = await axiosClient.patch(`/admin/announcements/${id}/`, payload);
    return data;
  },

  deleteAnnouncement: async (id) => {
    await axiosClient.delete(`/admin/announcements/${id}/`);
  },

  // The audit trail: how one record changed over time. Distinct from the audit log above,
  // which is the security record of who did what.
  getChangeLog: async (model, id) => {
    const { data } = await axiosClient.get(`/admin/audit-trail/${model}/${id}/`);
    return data;
  },

  // Read-only order lookup: D-033 keeps the admin out of individual orders, but support
  // still has to be able to answer a question about one.
  getOrders: async (params = {}) => {
    const { data } = await axiosClient.get('/admin/orders/', { params });
    return adaptPaginated(data);
  },

  getOrder: async (id) => {
    const { data } = await axiosClient.get(`/admin/orders/${id}/`);
    return data;
  },

  // Exports stream a file back, so the response is read as a blob and handed to the browser.
  exportCsv: async (kind, params = {}) => {
    const { data } = await axiosClient.get(`/admin/${kind}/export/`, {
      params,
      responseType: 'blob',
    });
    return data;
  },

  // The follow-up queue (admin-raised flags).
  getFlags: async (params = {}) => {
    const { data } = await axiosClient.get('/admin/flags/', { params });
    return adaptPaginated(data);
  },

  raiseFlag: async (payload) => {
    const { data } = await axiosClient.post('/admin/flags/', payload);
    return data;
  },

  resolveFlag: async (id, resolution) => {
    const { data } = await axiosClient.post(`/admin/flags/${id}/resolve/`, {
      resolution,
    });
    return data;
  },

  // Read only: these limits come from the environment, so changing one is a deploy.

  getSettings: async () => {
    const { data } = await axiosClient.get('/admin/settings/');
    return data;
  },

  getAuditLogs: async (params = {}) => {
    const { data } = await axiosClient.get('/admin/audit-logs/', { params });
    return adaptPaginated(data);
  },
};
