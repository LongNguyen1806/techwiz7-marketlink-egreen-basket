import axiosClient from '../../lib/axiosClient';

export const chatApi = {
  // CH-01. The request carries the current portal's token (or none for a guest); the backend
  // decides from it which lookups the assistant may use.
  send: async (messages) => {
    const { data } = await axiosClient.post('/chat/messages/', { messages });
    return data;
  },
};
