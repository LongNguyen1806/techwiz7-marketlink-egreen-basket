import axiosClient from '../../lib/axiosClient';
import { adaptPaginated } from '../../lib/adapters/pagination.adapter';

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

  getFarmerImpact: async (id) => {
    const { data } = await axiosClient.get(`/admin/farmers/${id}/deactivation-impact/`);
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

  updateFarmer: async (id, payload) => {
    const { data } = await axiosClient.patch(`/admin/farmers/${id}/`, payload);
    return data;
  },

  getCustomers: async (params = {}) => {
    const { data } = await axiosClient.get('/admin/customers/', { params });
    return adaptPaginated(data);
  },

  getCustomer: async (id) => {
    const { data } = await axiosClient.get(`/admin/customers/${id}/`);
    return data;
  },

  getCustomerImpact: async (id) => {
    const { data } = await axiosClient.get(`/admin/customers/${id}/deactivation-impact/`);
    return data;
  },

  updateCustomer: async (id, payload) => {
    const { data } = await axiosClient.patch(`/admin/customers/${id}/`, payload);
    return data;
  },

  deactivateCustomer: async (id, reason) => {
    const { data } = await axiosClient.post(`/admin/customers/${id}/deactivate/`, { reason });
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

  deactivateMarket: async (id, reason) => {
    const { data } = await axiosClient.post(`/admin/markets/${id}/deactivate/`, { reason });
    return data;
  },

  getMarketClosures: async (marketId, includePast = false) => {
    const { data } = await axiosClient.get(`/admin/markets/${marketId}/closures/`, {
      params: includePast ? { include_past: true } : undefined,
    });
    return data;
  },

  createMarketClosure: async (marketId, payload) => {
    const { data } = await axiosClient.post(`/admin/markets/${marketId}/closures/`, payload);
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
    const { data } = await axiosClient.post(`/admin/${reviewSegment(type)}/${id}/restore/`);
    return data;
  },

  getReports: async (params) => {
    const { data } = await axiosClient.get('/admin/reports/summary/', { params });
    return data;
  },

  exportReports: async (params) => {
    const response = await axiosClient.get('/admin/reports/export/', {
      params,
      responseType: 'blob',
    });
    return response.data;
  },

  getAnnouncements: async () => {
    const { data } = await axiosClient.get('/admin/announcements/');
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

  getChangeLog: async (model, id) => {
    const { data } = await axiosClient.get(`/admin/audit-trail/${model}/${id}/`);
    return data;
  },

  getAuditLogs: async (params = {}) => {
    const { data } = await axiosClient.get('/admin/audit-logs/', { params });
    return adaptPaginated(data);
  },
};
