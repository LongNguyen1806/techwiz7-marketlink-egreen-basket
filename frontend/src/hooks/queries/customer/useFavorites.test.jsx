import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import MockAdapter from 'axios-mock-adapter';
import axiosClient from '../../../lib/axiosClient';
import { QUERY_KEYS } from '../../../constants';
import { useAuthStore } from '../../../stores/auth.store';
import { useFavorites } from './useFavorites';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const ok = (data) => ({ success: true, message: 'OK', data, errors: {} });
const IDS = { farmer_ids: [3], product_ids: [], market_ids: [11] };

let mock;
let client;

function wrapper({ children }) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  mock = new MockAdapter(axiosClient);
  useAuthStore.getState().setTokens({ access: 'a', refresh: 'r', role: 'CUSTOMER' });
});

afterEach(() => {
  mock.restore();
  useAuthStore.getState().clearSession();
});

describe('useFavorites', () => {
  it('reads the three id lists once, so every heart in the app agrees (CU-12)', async () => {
    mock.onGet('/customer/favorite-ids/').reply(200, ok(IDS));
    const { result } = renderHook(() => useFavorites(), { wrapper });

    await waitFor(() => expect(result.current.isFavorite('farmers', 3)).toBe(true));
    expect(result.current.isFavorite('markets', 11)).toBe(true);
    expect(result.current.isFavorite('farmers', 4)).toBe(false);
    expect(result.current.isFavorite('products', 3)).toBe(false);
  });

  it('asks for nothing while nobody is signed in as a customer', async () => {
    useAuthStore.getState().clearSession();
    mock.onGet('/customer/favorite-ids/').reply(200, ok(IDS));
    renderHook(() => useFavorites(), { wrapper });

    
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(mock.history.get).toHaveLength(0);
  });

  it('fills the heart before the server answers, then keeps it filled', async () => {
    mock.onGet('/customer/favorite-ids/').reply(200, ok(IDS));
    let answer;
    mock.onPost('/customer/favorite-farmers/').reply(
      () => new Promise((resolve) => {
        answer = () => resolve([201, ok({ farmer_id: 7 })]);
      }),
    );
    const { result } = renderHook(() => useFavorites(), { wrapper });
    await waitFor(() => expect(result.current.isFavorite('farmers', 3)).toBe(true));

    act(() => {
      result.current.toggle({ kind: 'farmers', id: 7, isFavorite: false });
    });

    await waitFor(() => expect(result.current.isFavorite('farmers', 7)).toBe(true));
    expect(JSON.parse(mock.history.post[0].data)).toEqual({ farmer_id: 7 });

    mock.onGet('/customer/favorite-ids/').reply(200, ok({ ...IDS, farmer_ids: [3, 7] }));
    await act(async () => {
      answer();
    });
    await waitFor(() => expect(result.current.isFavorite('farmers', 7)).toBe(true));
  });

  it('puts the heart back when the request fails', async () => {
    
    
    
    let reads = 0;
    mock.onGet('/customer/favorite-ids/').reply(() => {
      reads += 1;
      return reads === 1 ? [200, ok(IDS)] : new Promise(() => {});
    });
    mock.onPost('/customer/favorite-products/').reply(500, {
      success: false, message: 'Server error', data: {}, errors: {},
    });
    const { result } = renderHook(() => useFavorites(), { wrapper });
    await waitFor(() => expect(result.current.isFavorite('farmers', 3)).toBe(true));

    await act(async () => {
      result.current.toggle({ kind: 'products', id: 5, isFavorite: false });
    });

    expect(client.getQueryData(QUERY_KEYS.FAVORITE_IDS)).toEqual(IDS);
  });

  it('drops a favourite through the id in the path', async () => {
    
    let stored = { ...IDS };
    mock.onGet('/customer/favorite-ids/').reply(() => [200, ok(stored)]);
    mock.onDelete('/customer/favorite-markets/11/').reply(() => {
      stored = { ...stored, market_ids: [] };
      return [204];
    });
    const { result } = renderHook(() => useFavorites(), { wrapper });
    await waitFor(() => expect(result.current.isFavorite('markets', 11)).toBe(true));

    await act(async () => {
      result.current.toggle({ kind: 'markets', id: 11, isFavorite: true });
    });

    await waitFor(() => expect(result.current.isFavorite('markets', 11)).toBe(false));
    expect(mock.history.delete.map((request) => request.url)).toEqual(['/customer/favorite-markets/11/']);
  });
});
