import axiosClient from '../../lib/axiosClient';
import { adaptMe } from '../../lib/adapters/auth.adapter';

/**
 * Auth endpoints, Pass 4B §4.1 (AU-01 → AU-09). `/auth/me/` already carries `farmer_status`
 * (§3.1 `Me`), so no screen needs a second request to learn it.
 */
function adaptLogin(raw) {
  return {
    access: raw.access,
    refresh: raw.refresh,
    user: adaptMe(raw.user),
  };
}

export const authApi = {
  /** AU-03. Customer and Farmer only; an admin account gets 401 here (D-027). */
  login: async (payload) => {
    const { data } = await axiosClient.post('/auth/login/', payload);
    return adaptLogin(data);
  },

  /** AU-09, the separate admin portal. */
  adminLogin: async (payload) => {
    const { data } = await axiosClient.post('/auth/admin/login/', payload);
    return adaptLogin(data);
  },

  /** AU-05. The backend revokes the session by its refresh token (D-021). */
  logout: async ({ refresh }) => {
    await axiosClient.post('/auth/logout/', { refresh });
  },

  /** AU-04. Rotation: the old refresh token dies with this call. */
  refresh: async (refresh) => {
    const { data } = await axiosClient.post('/auth/refresh/', { refresh });
    return data;
  },

  /** AU-06. */
  me: async () => {
    const { data } = await axiosClient.get('/auth/me/');
    return adaptMe(data);
  },

  /** AU-07. Keeps the current device signed in; every other device is signed out (D-021). */
  changePassword: async (payload) => {
    await axiosClient.post('/auth/change-password/', payload);
  },

  /** AU-08. One-time ticket for /ws/notifications/. */
  wsTicket: async () => {
    const { data } = await axiosClient.post('/auth/ws-ticket/', {});
    return data;
  },

  /** AU-01. Signs the new customer in straight away. */
  registerCustomer: async (payload) => {
    const { data } = await axiosClient.post('/auth/register/customer/', payload);
    return adaptLogin(data);
  },

  /** AU-02. The stall starts as PENDING until an admin approves it (D-015). */
  registerFarmer: async (payload) => {
    const { data } = await axiosClient.post('/auth/register/farmer/', payload);
    return adaptLogin(data);
  },
};
