import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { STORAGE_KEYS } from '../constants';

export const useGeoStore = create(
  persist(
    (set) => ({
      latitude: null,
      longitude: null,
      label: null,
      setCoords: (latitude, longitude, label) =>
        set({ latitude, longitude, label: label ?? 'My location' }),
      clear: () => set({ latitude: null, longitude: null, label: null }),
    }),
    { name: STORAGE_KEYS.GEO },
  ),
);
