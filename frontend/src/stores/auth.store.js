import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { STORAGE_KEYS } from '../constants/storageKeys';

// Two independent sessions per browser: the market portal (customers and farmers share /login,
// so they share one session) and the admin portal (/admin/*). Signing in, refreshing or signing
// out in one portal never touches the other.
export const PORTALS = Object.freeze({ MARKET: 'market', ADMIN: 'admin' });

const ADMIN_PREFIX = '/admin';
const ADMIN_STORAGE_KEY = `${STORAGE_KEYS.AUTH}.admin`;

export function portalForPath(pathname = '') {
  return pathname === ADMIN_PREFIX || pathname.startsWith(`${ADMIN_PREFIX}/`) ? PORTALS.ADMIN : PORTALS.MARKET;
}

/** The portal of the page this tab shows; outside React (axios) this is the source of truth. */
export function currentPortal() {
  return typeof window === 'undefined' ? PORTALS.MARKET : portalForPath(window.location.pathname);
}

function userIdFromToken(token) {
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(payload)).user_id ?? null;
  } catch {
    return null;
  }
}

const EMPTY_SESSION = { accessToken: null, refreshToken: null, userId: null };

function createSessionStore(storageKey) {
  return create(
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
        name: storageKey,
        storage: createJSONStorage(() => localStorage),
        partialize: ({ accessToken, refreshToken, userId }) => ({ accessToken, refreshToken, userId }),
      },
    ),
  );
}

export const useMarketAuthStore = createSessionStore(STORAGE_KEYS.AUTH);
export const useAdminAuthStore = createSessionStore(ADMIN_STORAGE_KEY);

// Kept for existing callers and tests: the market session.
export const useAuthStore = useMarketAuthStore;

const STORES = {
  [PORTALS.MARKET]: { store: useMarketAuthStore, storageKey: STORAGE_KEYS.AUTH },
  [PORTALS.ADMIN]: { store: useAdminAuthStore, storageKey: ADMIN_STORAGE_KEY },
};

export function authStoreFor(portal) {
  return (STORES[portal] ?? STORES[PORTALS.MARKET]).store;
}

export const selectIsAuthenticated = (state) => Boolean(state.accessToken && state.refreshToken);

// Tabs of the same portal stay in step; the other portal's session is left alone.
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    Object.values(STORES).forEach(({ store, storageKey }) => {
      if (event.key === storageKey) void store.persist.rehydrate();
    });
  });
}
