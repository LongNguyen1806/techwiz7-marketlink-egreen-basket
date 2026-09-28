import axiosClient from '../../lib/axiosClient';

export const chatApi = {
  send: async (messages) => {
    const { data } = await axiosClient.post('/chat/messages/', { messages });
    return data;
  },
};
