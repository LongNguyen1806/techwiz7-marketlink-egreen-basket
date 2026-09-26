import axiosClient from '../../lib/axiosClient';


export const announcementsApi = {
  list: async () => {
    const { data } = await axiosClient.get('/public/announcements/');
    return data;
  },
};
