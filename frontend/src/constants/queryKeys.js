// Query key factories. Keys are hierarchical so one prefix invalidates a whole family,
// e.g. invalidating farmerKeys.orders.all() refreshes every order list, detail and count.
// Filter objects sit last in a key; undefined properties are dropped when React Query
// hashes the key, so { q: undefined } and {} share one cache entry.

export const authKeys = {
  all: () => ['auth'],
  me: () => ['auth', 'me'],
};

export const publicKeys = {
  all: () => ['public'],
  config: () => ['public', 'config'],
  categories: () => ['public', 'categories'],
  markets: (params = {}) => ['public', 'markets', params],
};

export const notificationKeys = {
  all: () => ['notifications'],
  lists: () => ['notifications', 'list'],
  list: (params = {}) => ['notifications', 'list', params],
  latest: (limit) => ['notifications', 'latest', limit],
  unreadCount: () => ['notifications', 'unread-count'],
};

export const farmerKeys = {
  all: () => ['farmer'],
  dashboard: {
    all: () => ['farmer', 'dashboard'],
    range: (range = {}) => ['farmer', 'dashboard', range],
  },
  orders: {
    all: () => ['farmer', 'orders'],
    lists: () => ['farmer', 'orders', 'list'],
    list: (params = {}) => ['farmer', 'orders', 'list', params],
    detail: (id) => ['farmer', 'orders', 'detail', Number(id)],
    tabCounts: (params = {}) => ['farmer', 'orders', 'tab-counts', params],
    pickingList: (params = {}) => ['farmer', 'orders', 'picking-list', params],
  },
  products: {
    all: () => ['farmer', 'products'],
    lists: () => ['farmer', 'products', 'list'],
    list: (params = {}) => ['farmer', 'products', 'list', params],
    detail: (id) => ['farmer', 'products', 'detail', Number(id)],
    weeklyTemplate: () => ['farmer', 'products', 'weekly-template'],
  },
  markets: () => ['farmer', 'markets'],
  closures: () => ['farmer', 'closures'],
  profile: () => ['farmer', 'profile'],
  reviews: {
    all: () => ['farmer', 'reviews'],
    list: (params = {}) => ['farmer', 'reviews', 'list', params],
  },
};
