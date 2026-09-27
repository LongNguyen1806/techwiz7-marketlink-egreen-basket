import axiosClient from '../../lib/axiosClient';
import { adaptPaginated } from '../../lib/adapters/pagination.adapter';


export const catalogApi = {
  
  getConfig: async ({ signal } = {}) => {
    const { data } = await axiosClient.get('/public/config/', { signal });
    return data;
  },

  
  getCategories: async ({ signal } = {}) => {
    const { data } = await axiosClient.get('/public/categories/', { signal });
    return Array.isArray(data) ? data : [];
  },

  
  
  getMarkets: async (params = {}, { signal } = {}) => {
    const { data } = await axiosClient.get('/public/markets/', { params, signal });
    return adaptPaginated(data);
  },

  // MarketSummary + description, map_provider. With lat/lng, distance_km is filled in.
  getMarket: async (id, params = {}, { signal } = {}) => {
    const { data } = await axiosClient.get(`/public/markets/${id}/`, { params, signal });
    return data;
  },

  // APPROVED stalls selling at the market; params: { day, page, page_size }.
  // Each farmer's markets[] carries stall_label for this market.
  getMarketFarmers: async (id, params = {}, { signal } = {}) => {
    const { data } = await axiosClient.get(`/public/markets/${id}/farmers/`, { params, signal });
    return adaptPaginated(data);
  },

  
  
  getProducts: async (params = {}, { signal } = {}) => {
    const { data } = await axiosClient.get('/public/products/', { params, signal });
    return adaptPaginated(data);
  },

  
  getProduct: async (id, { signal } = {}) => {
    const { data } = await axiosClient.get(`/public/products/${id}/`, { signal });
    return data;
  },

  
  
  getProductReviews: async (id, params = {}, { signal } = {}) => {
    const { data } = await axiosClient.get(`/public/products/${id}/reviews/`, { params, signal });
    return { ...adaptPaginated(data), summary: data?.summary ?? null };
  },

  
  
  getFarmers: async (params = {}, { signal } = {}) => {
    const { data } = await axiosClient.get('/public/farmers/', { params, signal });
    return adaptPaginated(data);
  },

  // FarmerPublic: summary fields + contact_person, phone, address, description,
  // order_cutoff_hours, pickup_windows [{ market_id, market_name, stall_label, latitude, longitude, slots }].
  getFarmer: async (id, params = {}, { signal } = {}) => {
    const { data } = await axiosClient.get(`/public/farmers/${id}/`, { params, signal });
    return data;
  },

  // Same shape as product reviews: 10 per page plus `summary`.
  getFarmerReviews: async (id, params = {}, { signal } = {}) => {
    const { data } = await axiosClient.get(`/public/farmers/${id}/reviews/`, { params, signal });
    return { ...adaptPaginated(data), summary: data?.summary ?? null };
  },
};
