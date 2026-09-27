import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

import { STORAGE_KEYS } from '@/config/constants';

/**
 * Two independent sessions per browser.
 *
 * The market portal is everything a shopper or a stall sees; they share one sign-in screen, so
 * they share one session. The admin portal is `/admin/*` and keeps its own. Signing in,
 * refreshing or signing out in one never touches the other, which is what lets somebody hold
 * an admin session and a shopper session open in the same browser without one evicting the
 * other.
 *
 * The tokens live in the store, not in loose localStorage keys. With two sessions there is no
 * longer one "the access token", and a shared key would hand the wrong one to half the
 * requests.
 */
export const PORTALS = Object.freeze({ MARKET: 'market', ADMIN: 'admin' });

const ADMIN_PREFIX = '/admin';

export function portalForPath(pathname = '') {
  return pathname === ADMIN_PREFIX || pathname.startsWith(`${ADMIN_PREFIX}/`)
    ? PORTALS.ADMIN
    : PORTALS.MARKET;
}

/** The portal of the page this tab shows. Outside React (axios) this is the source of truth. */
export function currentPortal() {
  return typeof window === 'undefined'
    ? PORTALS.MARKET
    : portalForPath(window.location.pathname);
}

const EMPTY_SESSION = { accessToken: null, refreshToken: null, role: null };

function createSessionStore(storageKey) {
  return create()(
    persist(
      (set) => ({
        ...EMPTY_SESSION,

        setTokens: ({ access, refresh, role }) =>
          set((state) => ({
            accessToken: access,
            // A refresh response may rotate only the access token.
            refreshToken: refresh ?? state.refreshToken,
            role: role ?? state.role,
          })),

        setAccessToken: (access) => set({ accessToken: access }),

        setRole: (role) => set({ role }),

        clearSession: () => set(EMPTY_SESSION),
      }),
      {
        name: storageKey,
        storage: createJSONStorage(() => localStorage),
        partialize: ({ accessToken, refreshToken, role }) => ({
          accessToken,
          refreshToken,
          role,
        }),
      },
    ),
  );
}

export const useMarketAuthStore = createSessionStore(STORAGE_KEYS.AUTH);
export const useAdminAuthStore = createSessionStore(STORAGE_KEYS.AUTH_ADMIN);

// The market session under its old name, for the shopper-side code that only ever meant that
// one: favourites, the public header, the cart.
export const useAuthStore = useMarketAuthStore;

const STORES = {
  [PORTALS.MARKET]: { store: useMarketAuthStore, storageKey: STORAGE_KEYS.AUTH },
  [PORTALS.ADMIN]: { store: useAdminAuthStore, storageKey: STORAGE_KEYS.AUTH_ADMIN },
};

export function authStoreFor(portal) {
  return (STORES[portal] ?? STORES[PORTALS.MARKET]).store;
}

export const selectIsAuthenticated = (state) =>
  Boolean(state.accessToken && state.refreshToken);

export function hasHydrated() {
  return Object.values(STORES).every(({ store }) => store.persist.hasHydrated());
}

export function onHydrated(callback) {
  const pending = Object.values(STORES).filter(({ store }) => !store.persist.hasHydrated());
  if (pending.length === 0) {
    callback();
    return () => {};
  }
  let left = pending.length;
  const unsubscribes = pending.map(({ store }) =>
    store.persist.onFinishHydration(() => {
      left -= 1;
      if (left === 0) callback();
    }),
  );
  return () => unsubscribes.forEach((unsubscribe) => unsubscribe());
}

// Tabs showing the same portal stay in step; the other portal's session is left alone.
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    Object.values(STORES).forEach(({ store, storageKey }) => {
      if (event.key === storageKey) void store.persist.rehydrate();
    });
  });
}
