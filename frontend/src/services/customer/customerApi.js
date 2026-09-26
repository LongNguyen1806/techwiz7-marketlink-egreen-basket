import axiosClient from '../../lib/axiosClient';

/** Customer's own account and overview, Pass 4B §4.2 (CU-01 → CU-03). */
export const customerApi = {
  /** CU-01 (C-00). The backend sweeps overdue orders before counting, so the numbers are current. */
  dashboard: async () => {
    const { data } = await axiosClient.get('/customer/dashboard/');
    return data;
  },

  /** CU-02 (C-10). */
  profile: async () => {
    const { data } = await axiosClient.get('/customer/profile/');
    return data;
  },

  /** CU-03. Only the three writable fields; the serializer ignores anything else, email included. */
  updateProfile: async (payload) => {
    const { data } = await axiosClient.patch('/customer/profile/', payload);
    return data;
  },
};
