import axiosClient from '../../lib/axiosClient';

/**
 * PU-13 (N-04). Not paginated: it answers with the notices in force right now. A signed-in visitor
 * also gets the ones addressed to their role, which the backend works out from the token.
 */
export const announcementsApi = {
  list: async () => {
    const { data } = await axiosClient.get('/public/announcements/');
    return data;
  },
};
