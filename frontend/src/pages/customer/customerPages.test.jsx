import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import MockAdapter from 'axios-mock-adapter';
import axiosClient from '../../lib/axiosClient';
import { useAuthStore } from '../../stores/auth.store';
import { useCartStore } from '../../stores/cart.store';
import CustomerDashboard from './CustomerDashboard';
import FavoritesPage from './FavoritesPage';
import ProfilePage from './ProfilePage';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() } }));

const ok = (data) => ({ success: true, message: 'OK', data, errors: {} });
const failed = ({ message, errors = {}, code }) => ({ success: false, message, data: {}, errors, code });
const paged = (results) => ok({
  count: results.length, page: 1, page_size: 20, total_pages: 1, next: null, previous: null, results,
});

const FARMER = {
  id: 9, stall_name: 'Green Stall', image: null, rating_avg: 4.5, rating_count: 12,
  markets: [{ market_id: 2, market_name: 'Ben Thanh Market', stall_label: 'Row B, Stall 12' }],
  operating_days: [1, 3], in_stock_product_count: 8, upcoming_closures: [], distance_km: null,
  is_favorite: true,
};
const MARKET = {
  id: 2, name: 'Ben Thanh Market', address: '1 Le Loi Street', image: null,
  latitude: 10.772345, longitude: 106.698765, operating_days: [6, 7],
  open_time: '06:00', close_time: '18:00', upcoming_closures: [], farmer_count: 14,
  distance_km: null, is_favorite: true,
};
const ORDER = {
  id: 31, status: 'ACCEPTED', is_overdue: false, is_expiring_soon: false, has_pending_change: false,
  version: 2,
  customer: { id: 4, full_name: 'Alice Nguyen', phone: '0912345678' },
  farmer: { id: 9, stall_name: 'Green Stall', phone: '0987654321' },
  market: { id: 2, name: 'Ben Thanh Market', address: '1 Le Loi Street', latitude: 10.772345, longitude: 106.698765 },
  stall_label: 'Row B, Stall 12',
  pickup_date: '2026-10-02',
  pickup_start_at: '2026-10-02T06:00:00+07:00',
  pickup_end_at: '2026-10-02T09:00:00+07:00',
  cutoff_at: '2026-10-01T18:00:00+07:00',
  item_count: 3, total_amount: '24.50', created_at: '2026-09-26T08:00:00+07:00',
};
const DASHBOARD = {
  counts: { open: 2, ready_for_pickup: 1, completed: 7, pending_review: 3 },
  upcoming: [ORDER],
  favorite_farmers: [FARMER],
  favorite_markets: [MARKET],
  last_order_id: 30,
  recent_notifications: [
    {
      id: 5, type: 'ORDER_ACCEPTED', title: 'Order accepted',
      message: 'Green Stall accepted order #31', target_url: '/customer/orders/31',
      is_read: false, read_at: null, created_at: '2026-09-26T09:00:00+07:00',
    },
  ],
};
const PROFILE = {
  full_name: 'Alice Nguyen', phone: '0912345678',
  address: '12 Market Street, District 1', email: 'alice@example.com',
};
const EMPTY_IDS = { farmer_ids: [9], product_ids: [], market_ids: [2] };

let mock;

beforeEach(() => {
  mock = new MockAdapter(axiosClient);
  mock.onGet('/customer/favorite-ids/').reply(200, ok(EMPTY_IDS));
  useAuthStore.getState().setTokens({ access: 'a', refresh: 'r', role: 'CUSTOMER' });
});

afterEach(() => {
  mock.restore();
  useCartStore.getState().clear();
  useAuthStore.getState().clearSession();
});

function renderPage(ui) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('CustomerDashboard (C-00)', () => {
  it('shows the four counts CU-01 returns', async () => {
    mock.onGet('/customer/dashboard/').reply(200, ok(DASHBOARD));
    renderPage(<CustomerDashboard />);

    const ready = await screen.findByRole('link', { name: /ready for pickup/i });
    expect(ready).toHaveTextContent('1');
    expect(screen.getByRole('link', { name: /open orders/i })).toHaveTextContent('2');
    expect(screen.getByRole('link', { name: /completed/i })).toHaveTextContent('7');
    expect(screen.getByRole('link', { name: /to review/i })).toHaveTextContent('3');
  });

  it('names the stall, the market and the stall label of the next pickup', async () => {
    mock.onGet('/customer/dashboard/').reply(200, ok(DASHBOARD));
    renderPage(<CustomerDashboard />);

    const next = await screen.findByRole('region', { name: /next pickups/i });
    expect(within(next).getByText('Green Stall')).toBeInTheDocument();
    expect(within(next).getByText(/ben thanh market/i)).toBeInTheDocument();
    expect(within(next).getByText(/row b, stall 12/i)).toBeInTheDocument();
    expect(within(next).getByRole('link', { name: /directions/i })).toHaveAttribute(
      'href',
      'https://www.google.com/maps/dir/?api=1&destination=10.772345,106.698765',
    );
  });

  it('invites a first-time customer to the catalogue instead of showing empty boxes', async () => {
    mock.onGet('/customer/dashboard/').reply(200, ok({
      counts: { open: 0, ready_for_pickup: 0, completed: 0, pending_review: 0 },
      upcoming: [], favorite_farmers: [], favorite_markets: [], last_order_id: null,
      recent_notifications: [],
    }));
    renderPage(<CustomerDashboard />);

    expect(await screen.findByText(/you have no orders yet/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /browse products/i })).toHaveAttribute('href', '/products');
  });

  it('refills the cart from the last order at today\u2019s prices (CU-09)', async () => {
    mock.onGet('/customer/dashboard/').reply(200, ok(DASHBOARD));
    mock.onGet('/customer/orders/30/reorder-preview/').reply(200, ok({
      items: [{
        product: {
          id: 4, name: 'Da Lat lettuce', image: null, price: '13.00', unit: 'kg', stock_quantity: 10,
          is_available: true, availability: 'IN_STOCK', category: { id: 1, name: 'Vegetables' },
          farmer: { id: 9, stall_name: 'Green Stall' }, rating_avg: null, rating_count: 0, is_favorite: false,
        },
        quantity: 2,
      }],
      skipped: [],
    }));
    renderPage(<CustomerDashboard />);

    await userEvent.click(await screen.findByRole('button', { name: /reorder last order/i }));

    
    await waitFor(() => expect(useCartStore.getState().lines).toHaveLength(1));
    expect(useCartStore.getState().lines[0].price).toBe('13.00');
  });

  it('offers no reorder when there is no order to repeat', async () => {
    mock.onGet('/customer/dashboard/').reply(200, ok({ ...DASHBOARD, last_order_id: null }));
    renderPage(<CustomerDashboard />);

    await screen.findByRole('link', { name: /open orders/i });
    expect(screen.queryByRole('button', { name: /reorder last order/i })).not.toBeInTheDocument();
  });

  it('lists the latest notifications with a way into the full list', async () => {
    mock.onGet('/customer/dashboard/').reply(200, ok(DASHBOARD));
    renderPage(<CustomerDashboard />);

    expect(await screen.findByText('Green Stall accepted order #31')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /all notifications/i }))
      .toHaveAttribute('href', '/customer/notifications');
  });
});

describe('ProfilePage (C-10)', () => {
  it('fills the form from CU-02 and keeps email out of reach', async () => {
    mock.onGet('/customer/profile/').reply(200, ok(PROFILE));
    renderPage(<ProfilePage />);

    await waitFor(() => expect(screen.getByLabelText('Full name')).toHaveValue('Alice Nguyen'));
    expect(screen.getByLabelText('Phone number')).toHaveValue('0912345678');
    expect(screen.getByLabelText('Address')).toHaveValue('12 Market Street, District 1');
    
    expect(screen.getByLabelText('Email')).toBeDisabled();
  });

  it('sends only the fields that changed', async () => {
    mock.onGet('/customer/profile/').reply(200, ok(PROFILE));
    mock.onPatch('/customer/profile/').reply(200, ok({ ...PROFILE, phone: '0987654321' }));
    renderPage(<ProfilePage />);
    await waitFor(() => expect(screen.getByLabelText('Phone number')).toHaveValue('0912345678'));

    await userEvent.clear(screen.getByLabelText('Phone number'));
    await userEvent.type(screen.getByLabelText('Phone number'), '0987654321');
    await userEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => expect(mock.history.patch).toHaveLength(1));
    expect(JSON.parse(mock.history.patch[0].data)).toEqual({ phone: '0987654321' });
  });

  it('puts a rejected phone number under its own box', async () => {
    mock.onGet('/customer/profile/').reply(200, ok(PROFILE));
    mock.onPatch('/customer/profile/').reply(400, failed({
      message: 'Invalid input', errors: { phone: ['This phone number is already registered.'] },
    }));
    renderPage(<ProfilePage />);
    await waitFor(() => expect(screen.getByLabelText('Phone number')).toHaveValue('0912345678'));

    await userEvent.clear(screen.getByLabelText('Phone number'));
    await userEvent.type(screen.getByLabelText('Phone number'), '0987654321');
    await userEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      expect(screen.getByLabelText('Phone number'))
        .toHaveAccessibleDescription('This phone number is already registered.');
    });
  });
});

describe('FavoritesPage (C-08)', () => {
  it('opens on the stalls the customer saved', async () => {
    mock.onGet('/customer/favorite-farmers/').reply(200, paged([FARMER]));
    renderPage(<FavoritesPage />);

    expect(await screen.findByRole('link', { name: /green stall/i })).toBeInTheDocument();
  });

  it('loads a tab only when it is opened', async () => {
    mock.onGet('/customer/favorite-farmers/').reply(200, paged([FARMER]));
    mock.onGet('/customer/favorite-markets/').reply(200, paged([MARKET]));
    renderPage(<FavoritesPage />);
    await screen.findByRole('link', { name: /green stall/i });
    expect(mock.history.get.some((request) => request.url === '/customer/favorite-markets/')).toBe(false);

    await userEvent.click(screen.getByRole('tab', { name: /markets/i }));

    expect(await screen.findByRole('link', { name: /ben thanh market/i })).toBeInTheDocument();
  });

  it('says so when a tab holds nothing', async () => {
    mock.onGet('/customer/favorite-products/').reply(200, paged([]));
    mock.onGet('/customer/favorite-farmers/').reply(200, paged([FARMER]));
    renderPage(<FavoritesPage />);
    await screen.findByRole('link', { name: /green stall/i });

    await userEvent.click(screen.getByRole('tab', { name: /products/i }));

    expect(await screen.findByText(/nothing saved here yet/i)).toBeInTheDocument();
  });

  it('drops a stall the customer un-hearts (CU-15)', async () => {
    let farmers = [FARMER];
    mock.onGet('/customer/favorite-farmers/').reply(() => [200, paged(farmers)]);
    mock.onDelete('/customer/favorite-farmers/9/').reply(() => {
      farmers = [];
      return [204];
    });
    renderPage(<FavoritesPage />);
    await screen.findByRole('link', { name: /green stall/i });

    await userEvent.click(screen.getByRole('button', { name: /remove this farmer from favorites/i }));

    await waitFor(() => expect(screen.queryByRole('link', { name: /green stall/i })).not.toBeInTheDocument());
  });
});
