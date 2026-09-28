import { create } from 'zustand';

export const CHAT_HISTORY_LIMIT = 10;
export const CHAT_MESSAGE_MAX = 1000;

let sequence = 0;
const nextId = () => {
  sequence += 1;
  return `chat-${sequence}`;
};

export const useChatStore = create((set) => ({
  owner: null,
  open: false,
  messages: [],
  toolsUsed: [],

  setOpen: (open) => set({ open }),

  claim: (owner) =>
    set((state) => (state.owner === owner ? state : { owner, messages: [], toolsUsed: [] })),

  add: (role, content, extra = {}) =>
    set((state) => ({ messages: [...state.messages, { id: nextId(), role, content, ...extra }] })),

  setToolsUsed: (toolsUsed) => set({ toolsUsed }),

  reset: () => set({ messages: [], toolsUsed: [] }),
}));
