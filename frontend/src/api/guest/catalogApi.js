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
};
