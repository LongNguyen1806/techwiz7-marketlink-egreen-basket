




export const authKeys = {
  all: () => ['auth'],
  me: () => ['auth', 'me'],
};

export const publicKeys = {
  all: () => ['public'],
  config: () => ['public', 'config'],
  categories: () => ['public', 'categories'],
  markets: (params = {}) => ['public', 'markets', params],
  products: (params = {}) => ['public', 'products', params],
  
  productList: (params = {}) => ['public', 'products', 'list', params],
  product: (id) => ['public', 'products', 'detail', Number(id)],
  productReviews: (id, params = {}) => ['public', 'products', 'reviews', Number(id), params],
  farmers: (params = {}) => ['public', 'farmers', params],
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
    tabCounts: () => ['farmer', 'orders', 'tab-counts'],
    pickingLists: () => ['farmer', 'orders', 'picking-list'],
    pickingList: (pickupDate) => ['farmer', 'orders', 'picking-list', pickupDate],
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

export const QUERY_KEYS = {
  ME: ['me'],
  PUBLIC_CONFIG: ['public-config'],
  CATEGORIES: ['categories'],
  MARKETS: (params) => ['markets', params],
  MARKET: (id) => ['market', String(id)],
  MARKET_FARMERS: (id) => ['market-farmers', String(id)],
  FARMERS: (params) => ['farmers', params],
  FARMER: (id) => ['farmer', String(id)],
  FARMER_PICKUP: (id) => ['farmer-pickup', String(id)],
  FARMER_REVIEWS: (id) => ['farmer-reviews', String(id)],
  FARMER_PRODUCTS: (id) => ['farmer-products', String(id)],
  FARMER_RATING: (id) => ['farmer-rating', String(id)],
  PRODUCTS: (params) => ['products', params],
  PRODUCT: (id) => ['product', String(id)],
  PRODUCT_REVIEWS: (id) => ['product-reviews', String(id)],
  PRODUCT_RATING: (id) => ['product-rating', String(id)],
  SEARCH: (q) => ['search', q],
  CUSTOMER_DASHBOARD: ['customer-dashboard'],
  CUSTOMER_PROFILE: ['customer-profile'],
  ORDERS: (params) => ['orders', params],
  ORDER: (id) => ['order', String(id)],
  NOTIFICATIONS_LIST: ['notifications-list'],
  NOTIFICATIONS_PAGE: (params) => ['notifications-page', params],
  FARMER_DASHBOARD: (params) => ['farmer-dashboard', params],
  FARMER_ORDER_COUNTS: ['farmer-order-counts'],
  FARMER_ORDERS: (params) => ['farmer-orders', params],
  FARMER_ORDER: (id) => ['farmer-order', String(id)],
  FARMER_PICKING: (date) => ['farmer-picking', date],
  FARMER_MY_PRODUCTS: (params) => ['farmer-my-products', params],
  FARMER_MY_PRODUCT: (id) => ['farmer-my-product', String(id)],
  FARMER_STOCK_PREVIEW: ['farmer-stock-preview'],
  FARMER_MARKETS: ['farmer-markets'],
  FARMER_PROFILE: ['farmer-profile'],
  FARMER_MY_REVIEWS: (params) => ['farmer-my-reviews', params],
  ADMIN_DASHBOARD: ['admin-dashboard'],
  ADMIN_FARMERS: (params) => ['admin-farmers', params],
  ADMIN_FARMER: (id) => ['admin-farmer', String(id)],
  ADMIN_FARMER_IMPACT: (id) => ['admin-farmer-impact', String(id)],
  ADMIN_CUSTOMERS: (params) => ['admin-customers', params],
  ADMIN_CUSTOMER_IMPACT: (id) => ['admin-customer-impact', String(id)],
  ADMIN_MARKETS: (params) => ['admin-markets', params],
  ADMIN_MARKET: (id) => ['admin-market', String(id)],
  ADMIN_CATEGORIES: ['admin-categories'],
  ADMIN_MODERATION_PRODUCTS: ['admin-mod-products'],
  ADMIN_MODERATION_REVIEWS: ['admin-mod-reviews'],
  ADMIN_REPORTS: (params) => ['admin-reports', params],
  ADMIN_ANNOUNCEMENTS: ['admin-announcements'],
  ADMIN_AUDIT_LOGS: (params) => ['admin-audit-logs', params],
  ANNOUNCEMENTS: ['announcements'],
  FAVORITE_IDS: ['favorite-ids'],
  CUSTOMER_FAVORITES: (kind, page) => ['customer-favorites', kind, page],
  FAVORITE_MARKET: (id) => ['favorite-market', String(id)],
  FAVORITE_FARMER: (id) => ['favorite-farmer', String(id)],
  FAVORITE_PRODUCTS: (ids) => ['favorite-products', ids],
};

