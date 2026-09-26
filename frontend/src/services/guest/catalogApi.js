import axiosClient from '../../lib/axiosClient';


export const MAX_IDS = 50;


export const catalogApi = {
  products: async ({ ids, ...params } = {}) => {
    const query = { ...params };
    if (ids?.length) query.ids = ids.slice(0, MAX_IDS).join(',');
    const { data } = await axiosClient.get('/public/products/', { params: query });
    return data;
  },
};
