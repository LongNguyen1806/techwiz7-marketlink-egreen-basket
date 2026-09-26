import axiosClient from '../../lib/axiosClient';


const PATH = {
  farmers: '/customer/favorite-farmers/',
  products: '/customer/favorite-products/',
  markets: '/customer/favorite-markets/',
};


const ID_FIELD = { farmers: 'farmer_id', products: 'product_id', markets: 'market_id' };
export const IDS_FIELD = { farmers: 'farmer_ids', products: 'product_ids', markets: 'market_ids' };

export const FAVORITE_KINDS = Object.keys(PATH);

export const favoritesApi = {
  
  ids: async () => {
    const { data } = await axiosClient.get('/customer/favorite-ids/');
    return data;
  },

  
  list: async ({ kind, page = 1 }) => {
    const { data } = await axiosClient.get(PATH[kind], { params: { page } });
    return data;
  },

  
  add: async ({ kind, id }) => {
    const { data } = await axiosClient.post(PATH[kind], { [ID_FIELD[kind]]: id });
    return data;
  },

  
  remove: async ({ kind, id }) => {
    await axiosClient.delete(`${PATH[kind]}${id}/`);
  },
};
