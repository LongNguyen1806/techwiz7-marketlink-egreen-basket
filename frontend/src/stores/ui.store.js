import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { STORAGE_KEYS } from '../constants/storageKeys';

function applyTheme(theme) {
  document.documentElement.classList.toggle('dark', theme === 'dark');
}

export const useUiStore = create(
  persist(
    (set, get) => ({
      theme: 'light',
      sidebarCollapsed: false,
      mobileNavOpen: false,
      // True while the notification WebSocket is open; polling is the fallback otherwise.
      realtimeConnected: false,

      setTheme: (theme) => {
        applyTheme(theme);
        set({ theme });
      },
      toggleTheme: () => get().setTheme(get().theme === 'dark' ? 'light' : 'dark'),
      setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
      setMobileNavOpen: (mobileNavOpen) => set({ mobileNavOpen }),
      setRealtimeConnected: (realtimeConnected) => set({ realtimeConnected }),
    }),
    {
      name: STORAGE_KEYS.UI,
      storage: createJSONStorage(() => localStorage),
      partialize: ({ theme, sidebarCollapsed }) => ({ theme, sidebarCollapsed }),
      onRehydrateStorage: () => (state) => {
        if (state) applyTheme(state.theme);
      },
    },
  ),
);
