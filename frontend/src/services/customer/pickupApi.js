import axiosClient from '../../lib/axiosClient';

/**
 * PU-08 (C-02, C-06, G-06): the days and windows a stall can actually be collected from.
 *
 * The backend has already removed everything unbookable — days the market is shut, days the stall
 * rests (D-023), days outside the booking horizon, and any window whose cut-off has passed (D-007) —
 * so whatever comes back can be offered as is.
 */
export const pickupApi = {
  options: async ({ farmerId, from, days } = {}) => {
    const params = {};
    if (from) params.from = from;
    if (days) params.days = days;
    const { data } = await axiosClient.get(`/public/farmers/${farmerId}/pickup-options/`, { params });
    return data;
  },
};
