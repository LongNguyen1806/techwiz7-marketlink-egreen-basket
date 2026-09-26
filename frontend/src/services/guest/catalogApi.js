import axiosClient from '../../lib/axiosClient';

/** PU-10 accepts at most 50 ids in one call. */
export const MAX_IDS = 50;

/**
 * Public catalogue (Pass 4B §4.4). Paginated like every list endpoint: `{ count, …, results }`.
 *
 * With `ids` it is the cart refresh of C-01, and then it behaves differently on purpose: sold-out
 * and paused products still come back so the cart can grey them out, while archived or removed ones
 * are simply absent.
 */
export const catalogApi = {
  products: async ({ ids, ...params } = {}) => {
    const query = { ...params };
    if (ids?.length) query.ids = ids.slice(0, MAX_IDS).join(',');
    const { data } = await axiosClient.get('/public/products/', { params: query });
    return data;
  },
};
