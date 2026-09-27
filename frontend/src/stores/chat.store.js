import { create } from 'zustand';

// Sent to the assistant with every question (CH-01 accepts up to 10).
export const CHAT_HISTORY_LIMIT = 10;
export const CHAT_MESSAGE_MAX = 1000;

let sequence = 0;
const nextId = () => {
  sequence += 1;
  return `chat-${sequence}`;
};

/**
 * The assistant conversation. In memory only (D-011: no history on the server, none in the
 * browser either): it survives moving between pages and is gone on reload. `owner` is who it
 * belongs to; signing in as someone else starts a new conversation, so one person's order or
 * stall details never show to the next.
 */
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
