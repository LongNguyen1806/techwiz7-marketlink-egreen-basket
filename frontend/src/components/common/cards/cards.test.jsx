import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import MockAdapter from 'axios-mock-adapter';
import axiosClient from '../../../lib/axiosClient';
import { useAuthStore } from '../../../stores/auth.store';
import { FarmerCard } from './FarmerCard';
import { MarketCard } from './MarketCard';
import { ProductCard } from './ProductCard';
import { FavoriteButton } from '../favorites/FavoriteButton';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() } }));


const FARMER = {
  id: 9,
  stall_name: 'Green Stall',
  image: null,
  rating_avg: 4.67,
  rating_count: 12,
  markets: [{ market_id: 2, market_name: 'Ben Thanh Market', stall_label: 'Row B, Stall 12' }],
  operating_days: [1, 3, 5],
  in_stock_product_count: 8,
  upcoming_closures: [],
  distance_km: 2.4,
  is_favorite: true,
};
const PRODUCT = {
  id: 4,
  name: 'Da Lat lettuce',
  image: null,
  price: '12.50',
  unit: 'kg',
  stock_quantity: 6,
  is_available: true,
  availability: 'IN_STOCK',
  category: { id: 1, name: 'Vegetables' },
  farmer: { id: 9, stall_name: 'Green Stall' },
  rating_avg: null,
  rating_count: 0,
  is_favorite: false,
};
const MARKET = {
  id: 2,
  name: 'Ben Thanh Market',
  address: '1 Le Loi Street',
  image: null,
  latitude: 10.772345,
  longitude: 106.698765,
  operating_days: [6, 7],
  open_time: '06:00',
  close_time: '18:00',
  upcoming_closures: [],
  farmer_count: 14,
  distance_km: null,
  is_favorite: true,
};

const ok = (data) => ({ success: true, message: 'OK', data, errors: {} });

let mock;
let stored;

beforeEach(() => {
  mock = new MockAdapter(axiosClient);
  
  stored = { farmer_ids: [9], product_ids: [], market_ids: [2] };
  mock.onGet('/customer/favorite-ids/').reply(() => [200, ok(stored)]);
  useAuthStore.getState().setTokens({ access: 'a', refresh: 'r', role: 'CUSTOMER' });
});

afterEach(() => {
  mock.restore();
  useAuthStore.getState().clearSession();
});

function renderCard(ui) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('ProductCard', () => {
  it('reads the decimal string as money and names the stall behind it', () => {
    renderCard(<ProductCard product={PRODUCT} />);

    expect(screen.getByText('$12.50')).toBeInTheDocument();
    expect(screen.getByText('/kg')).toBeInTheDocument();
    expect(screen.getByText('Green Stall')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /da lat lettuce/i })).toHaveAttribute('href', '/products/4');
  });

  it('hands the whole product to the cart, so the caller owns the quantity', async () => {
    const onAddToCart = vi.fn();
    renderCard(<ProductCard product={PRODUCT} onAddToCart={onAddToCart} />);

    await userEvent.click(screen.getByRole('button', { name: /cart/i }));

    expect(onAddToCart).toHaveBeenCalledWith(PRODUCT);
  });

  it('offers a restock alert instead of a cart button when it is sold out (D-025)', () => {
    const soldOut = { ...PRODUCT, stock_quantity: 0, availability: 'OUT_OF_STOCK' };
    renderCard(<ProductCard product={soldOut} onAddToCart={vi.fn()} />);

    expect(screen.getByRole('button', { name: /cart/i })).toBeDisabled();
    expect(screen.getByText(/notify when back in stock/i)).toBeInTheDocument();
  });

  it('says nothing about restocking a product the seller paused', () => {
    const paused = { ...PRODUCT, is_available: false, availability: 'UNAVAILABLE' };
    renderCard(<ProductCard product={paused} onAddToCart={vi.fn()} />);

    expect(screen.getByRole('button', { name: /cart/i })).toBeDisabled();
    expect(screen.queryByText(/notify when back in stock/i)).not.toBeInTheDocument();
  });
});

describe('FarmerCard', () => {
  it('shows the rating, the stock count and the days the stall is open', () => {
    renderCard(<FarmerCard farmer={FARMER} />);

    expect(screen.getByText('4.7')).toBeInTheDocument();
    expect(screen.getByText('(12)')).toBeInTheDocument();
    expect(screen.getByText(/8 products in stock/i)).toBeInTheDocument();
    expect(screen.getByText('Mon')).toBeInTheDocument();
    expect(screen.getByText('Wed')).toBeInTheDocument();
    expect(screen.getByText('Fri')).toBeInTheDocument();
    expect(screen.queryByText('Tue')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /green stall/i })).toHaveAttribute('href', '/farmers/9');
  });

  it('leaves the rating blank rather than printing a zero it never earned', () => {
    renderCard(<FarmerCard farmer={{ ...FARMER, rating_avg: null, rating_count: 0 }} />);

    expect(screen.getByText('—')).toBeInTheDocument();
  });
});

describe('MarketCard', () => {
  it('shows the opening hours and links out for directions', () => {
    renderCard(<MarketCard market={MARKET} />);

    expect(screen.getByText(/06:00–18:00 · 14 stalls/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /directions/i })).toHaveAttribute(
      'href',
      'https://www.google.com/maps/dir/?api=1&destination=10.772345,106.698765',
    );
    expect(screen.getByRole('link', { name: /ben thanh market/i })).toHaveAttribute('href', '/markets/2');
  });
});

describe('FavoriteButton', () => {
  it('reports what it holds, so a screen reader hears the state', async () => {
    renderCard(<FavoriteButton kind="farmers" id={9} isFavorite />);

    await waitFor(() => expect(screen.getByRole('button')).toHaveAttribute('aria-pressed', 'true'));
  });

  it('drops a favourite the customer already has', async () => {
    mock.onDelete('/customer/favorite-farmers/9/').reply(() => {
      stored = { ...stored, farmer_ids: [] };
      return [204];
    });
    renderCard(<FavoriteButton kind="farmers" id={9} isFavorite />);
    await waitFor(() => expect(screen.getByRole('button')).toHaveAttribute('aria-pressed', 'true'));

    await userEvent.click(screen.getByRole('button'));

    await waitFor(() => expect(mock.history.delete).toHaveLength(1));
    expect(screen.getByRole('button')).toHaveAttribute('aria-pressed', 'false');
  });

  it('asks a guest to sign in rather than sending a request that would be refused', async () => {
    useAuthStore.getState().clearSession();
    const onRequireSignIn = vi.fn();
    renderCard(<FavoriteButton kind="markets" id={2} isFavorite={null} onRequireSignIn={onRequireSignIn} />);

    await userEvent.click(screen.getByRole('button'));

    expect(onRequireSignIn).toHaveBeenCalled();
    expect(mock.history.post).toHaveLength(0);
    expect(mock.history.delete).toHaveLength(0);
  });
});
