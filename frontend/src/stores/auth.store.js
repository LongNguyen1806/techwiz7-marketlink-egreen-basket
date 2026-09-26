import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { STORAGE_KEYS } from '../constants/storageKeys';






function userIdFromToken(token) {
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(payload)).user_id ?? null;
  } catch {
    return null;
  }
}

const EMPTY_SESSION = { accessToken: null, refreshToken: null, userId: null };

export const useAuthStore = create(
  persist(
    (set) => ({
      ...EMPTY_SESSION,
      setTokens: ({ access, refresh }) =>
        set((state) => ({
          accessToken: access,
          refreshToken: refresh ?? state.refreshToken,
          userId: userIdFromToken(access),
        })),
      clearSession: () => set(EMPTY_SESSION),
    }),
    {
      name: STORAGE_KEYS.AUTH,
      storage: createJSONStorage(() => localStorage),
      partialize: ({ accessToken, refreshToken, userId }) => ({ accessToken, refreshToken, userId }),
    },
  ),
);

export const selectIsAuthenticated = (state) => Boolean(state.accessToken && state.refreshToken);


if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    if (event.key === STORAGE_KEYS.AUTH) void useAuthStore.persist.rehydrate();
  });
}
