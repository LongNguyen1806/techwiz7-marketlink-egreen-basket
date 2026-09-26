import axiosClient from '../../lib/axiosClient';

/**
 * Favourites, Pass 4B §4.2 (CU-12 → CU-17). The three kinds share one shape, so the screens name a
 * kind rather than repeating three near-identical calls.
 */
const PATH = {
  farmers: '/customer/favorite-farmers/',
  products: '/customer/favorite-products/',
  markets: '/customer/favorite-markets/',
};

/** The body key each POST expects, and the key of the matching list in CU-12. */
const ID_FIELD = { farmers: 'farmer_id', products: 'product_id', markets: 'market_id' };
export const IDS_FIELD = { farmers: 'farmer_ids', products: 'product_ids', markets: 'market_ids' };

export const FAVORITE_KINDS = Object.keys(PATH);

export const favoritesApi = {
  /** CU-12: every id at once, for the hearts scattered across the catalogue. */
  ids: async () => {
    const { data } = await axiosClient.get('/customer/favorite-ids/');
    return data;
  },

  /** CU-13 / CU-16 / CU-17 (C-08). Paginated: `{ count, page, …, results }`. */
  list: async ({ kind, page = 1 }) => {
    const { data } = await axiosClient.get(PATH[kind], { params: { page } });
    return data;
  },

  /** CU-14 / CU-16 / CU-17. */
  add: async ({ kind, id }) => {
    const { data } = await axiosClient.post(PATH[kind], { [ID_FIELD[kind]]: id });
    return data;
  },

  /** CU-15 / CU-16 / CU-17. */
  remove: async ({ kind, id }) => {
    await axiosClient.delete(`${PATH[kind]}${id}/`);
  },
};
