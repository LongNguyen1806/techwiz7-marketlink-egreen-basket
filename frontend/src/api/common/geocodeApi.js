import axiosClient from '../../lib/axiosClient';

export const geocodeApi = {
  // An address to a point on the map: { found, latitude, longitude }. Open to guests (the
  // sign-up form uses it) and throttled on the server.
  lookup: async (q) => {
    const { data } = await axiosClient.get('/public/geocode/', { params: { q } });
    return data;
  },
};
