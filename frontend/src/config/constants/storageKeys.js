export const STORAGE_KEYS = {
  // One key per portal. Tokens live inside these persisted sessions rather than in loose
  // ACCESS/REFRESH keys: with an admin session and a market session open at once there is no
  // single "the access token", and a shared key would hand the wrong one to half the requests.
  AUTH: 'marketlink-auth',
  AUTH_ADMIN: 'marketlink-auth.admin',
  THEME: 'marketlink-theme',
  UI: 'marketlink-ui',
  CART: 'marketlink-cart',
  GEO: 'marketlink-geo',
};
