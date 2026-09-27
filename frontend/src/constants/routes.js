import { ROLES } from './roles';

export const ROUTES = Object.freeze({
  HOME: '/',
  LOGIN: '/login',
  REGISTER_CUSTOMER: '/register',
  REGISTER_FARMER: '/register/farmer',
  FORBIDDEN: '/403',

  FARMER: Object.freeze({
    HOME: '/farmer',
    ORDERS: '/farmer/orders',
    ORDER: (id) => `/farmer/orders/${id}`,
    PRODUCTS: '/farmer/products',
    PRODUCT_NEW: '/farmer/products/new',
    PRODUCT_EDIT: (id) => `/farmer/products/${id}/edit`,
    STOCK_TEMPLATE: '/farmer/stock-template',
    MARKETS: '/farmer/markets',
    PROFILE: '/farmer/profile',
    REVIEWS: '/farmer/reviews',
    STATS: '/farmer/stats',
    NOTIFICATIONS: '/farmer/notifications',
    CHANGE_PASSWORD: '/farmer/settings',
  }),

  
  CUSTOMER: Object.freeze({
    HOME: '/',
    ORDERS: '/customer/orders',
    PROFILE: '/customer/profile',
    FAVORITES: '/customer/favorites',
    NOTIFICATIONS: '/customer/notifications',
    
    CHANGE_PASSWORD: '/customer/password',
  }),

  ADMIN: Object.freeze({
    HOME: '/admin',
    LOGIN: '/admin/login',
  }),
});

export const DASHBOARD_PATH = Object.freeze({
  [ROLES.CUSTOMER]: ROUTES.CUSTOMER.HOME,
  [ROLES.FARMER]: ROUTES.FARMER.HOME,
  [ROLES.ADMIN]: ROUTES.ADMIN.HOME,
});

export function homePathForRole(role) {
  return DASHBOARD_PATH[role] ?? ROUTES.HOME;
}
