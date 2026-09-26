import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import MockAdapter from 'axios-mock-adapter';
import axiosClient from '../../lib/axiosClient';
import { useAuthStore } from '../../stores/auth.store';
import { useCartStore } from '../../stores/cart.store';
import CartPage from './CartPage';
import CheckoutPage from './CheckoutPage';
import CheckoutSuccessPage from './CheckoutSuccessPage';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() } }));

const ok = (data) => ({ success: true, message: 'OK', data, errors: {} });
const failed = ({ message, errors = {}, code, data = {} }) => ({ success: false, message, data, errors, code });
const paged = (results) => ok({
  count: results.length, page: 1, page_size: 20, total_pages: 1, next: null, previous: null, results,
});

const LETTUCE = {
  product_id: 4, farmer_id: 9, farmer_stall_name: 'Green Stall',
  name: 'Da Lat lettuce', unit: 'kg', price: '12.50', image: null,
};
const MANGO = {
  product_id: 7, farmer_id: 11, farmer_stall_name: 'Sunny Orchard',
  name: 'Mango', unit: 'kg', price: '8.00', image: null,
};


const CATALOGUE = [
  {
    id: 4, name: 'Da Lat lettuce', price: '12.50', unit: 'kg', image: null, stock_quantity: 20,
    is_available: true, availability: 'IN_STOCK', category: { id: 1, name: 'Vegetables' },
    farmer: { id: 9, stall_name: 'Green Stall' }, rating_avg: null, rating_count: 0, is_favorite: false,
  },
  {
    id: 7, name: 'Mango', price: '8.00', unit: 'kg', image: null, stock_quantity: 20,
    is_available: true, availability: 'IN_STOCK', category: { id: 2, name: 'Fruit' },
    farmer: { id: 11, stall_name: 'Sunny Orchard' }, rating_avg: null, rating_count: 0, is_favorite: false,
  },
];

const GREEN_STALL_OPTIONS = [{
  market_id: 2, market_name: 'Ben Thanh Market', stall_label: 'Row B, Stall 12',
  latitude: 10.772345, longitude: 106.698765,
  dates: [{
    date: '2026-10-02', day_of_week: 5,
    slots: [
      { pickup_slot_id: 40, start_time: '06:00', end_time: '09:00', cutoff_at: '2026-10-01T18:00:00+07:00', is_bookable: true },
      { pickup_slot_id: 41, start_time: '15:00', end_time: '18:00', cutoff_at: '2026-10-01T18:00:00+07:00', is_bookable: true },
    ],
  }],
}];
const ORCHARD_OPTIONS = [{
  market_id: 3, market_name: 'Tan Dinh Market', stall_label: 'Row A, Stall 4',
  latitude: 10.79, longitude: 106.69,
  dates: [{
    date: '2026-10-03', day_of_week: 6,
    slots: [
      { pickup_slot_id: 55, start_time: '07:00', end_time: '10:00', cutoff_at: '2026-10-02T18:00:00+07:00', is_bookable: true },
    ],
  }],
}];

const PLACED_ORDER = {
  id: 31, status: 'PLACED', is_overdue: false, is_expiring_soon: false, has_pending_change: false, version: 1,
  customer: { id: 4, full_name: 'Alice Nguyen', phone: '0912345678' },
  farmer: { id: 9, stall_name: 'Green Stall', phone: '0987654321' },
  market: { id: 2, name: 'Ben Thanh Market', address: '1 Le Loi Street', latitude: 10.772345, longitude: 106.698765 },
  stall_label: 'Row B, Stall 12', pickup_date: '2026-10-02',
  pickup_start_at: '2026-10-02T06:00:00+07:00', pickup_end_at: '2026-10-02T09:00:00+07:00',
  cutoff_at: '2026-10-01T18:00:00+07:00', item_count: 2, total_amount: '25.00',
  created_at: '2026-09-26T08:00:00+07:00',
};

let mock;

beforeEach(() => {
  mock = new MockAdapter(axiosClient);
  mock.onGet('/public/products/').reply(200, paged(CATALOGUE));
  mock.onGet('/public/farmers/9/pickup-options/').reply(200, ok(GREEN_STALL_OPTIONS));
  mock.onGet('/public/farmers/11/pickup-options/').reply(200, ok(ORCHARD_OPTIONS));
  useAuthStore.getState().setTokens({ access: 'a', refresh: 'r', role: 'CUSTOMER' });
  useCartStore.getState().clear();
});

afterEach(() => {
  mock.restore();
  useCartStore.getState().clear();
  useAuthStore.getState().clearSession();
});

function renderAt(path, ui, state) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[{ pathname: path, state }]}>
        <Routes>
          <Route path="/customer/cart" element={<CartPage />} />
          <Route path="/customer/checkout" element={<CheckoutPage />} />
          <Route path="/customer/checkout/success" element={<CheckoutSuccessPage />} />
        </Routes>
        {ui}
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function fillCart() {
  useCartStore.getState().addItem(LETTUCE, 2);
  useCartStore.getState().addItem(MANGO, 3);
}

describe('CartPage (C-01)', () => {
  it('groups the lines by farmer and totals each group', async () => {
    fillCart();
    renderAt('/customer/cart');

    const green = await screen.findByRole('region', { name: /green stall/i });
    expect(within(green).getByText('Da Lat lettuce')).toBeInTheDocument();
    expect(within(green).queryByText('Mango')).not.toBeInTheDocument();
    
    expect(screen.getByTestId('cart-subtotal-9')).toHaveTextContent('$25.00');
    expect(screen.getByTestId('cart-subtotal-11')).toHaveTextContent('$24.00');
    expect(screen.getByTestId('cart-total')).toHaveTextContent('$49.00');
  });

  it('says payment happens at the market, because no money moves online', async () => {
    fillCart();
    renderAt('/customer/cart');

    expect(await screen.findByText(/pay in cash when you pick up/i)).toBeInTheDocument();
  });

  it('takes the fresh price from PU-10 rather than the one saved in the cart', async () => {
    useCartStore.getState().addItem({ ...LETTUCE, price: '9.00' }, 2);
    renderAt('/customer/cart');

    
    await waitFor(() => expect(screen.getByTestId('cart-total')).toHaveTextContent('$25.00'));
  });

  it('greys out a product that left the catalogue and keeps it out of the total', async () => {
    mock.onGet('/public/products/').reply(200, paged([CATALOGUE[1]]));
    fillCart();
    renderAt('/customer/cart');

    await waitFor(() => expect(screen.getByText(/unavailable/i)).toBeInTheDocument());
    expect(screen.getByTestId('cart-total')).toHaveTextContent('$24.00');
  });

  it('warns when the cart asks for more than the stall has left', async () => {
    mock.onGet('/public/products/').reply(200, paged([{ ...CATALOGUE[0], stock_quantity: 1 }, CATALOGUE[1]]));
    fillCart();
    renderAt('/customer/cart');

    expect(await screen.findByText(/only 1 kg left/i)).toBeInTheDocument();
  });

  it('sends an empty cart back to the catalogue', async () => {
    renderAt('/customer/cart');

    expect(await screen.findByText(/your cart is empty/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /browse products/i })).toHaveAttribute('href', '/products');
  });

  it('removes a line when asked', async () => {
    fillCart();
    renderAt('/customer/cart');
    await screen.findByText('Da Lat lettuce');

    await userEvent.click(screen.getByRole('button', { name: /remove da lat lettuce/i }));

    expect(screen.queryByText('Da Lat lettuce')).not.toBeInTheDocument();
    expect(useCartStore.getState().lines).toHaveLength(1);
  });
});

describe('CheckoutPage (C-02)', () => {
  async function chooseSlots() {
    await userEvent.click(await screen.findByRole('radio', { name: /06:00–09:00/ }));
    await userEvent.click(screen.getByRole('radio', { name: /07:00–10:00/ }));
  }

  it('will not place anything until every stall has a pickup window', async () => {
    fillCart();
    renderAt('/customer/checkout');

    const confirm = await screen.findByRole('button', { name: /confirm 2 orders/i });
    expect(confirm).toBeDisabled();

    await chooseSlots();

    expect(screen.getByRole('button', { name: /confirm 2 orders/i })).toBeEnabled();
  });

  it('refuses a window whose cut-off has already gone by (D-007)', async () => {
    mock.onGet('/public/farmers/9/pickup-options/').reply(200, ok([{
      ...GREEN_STALL_OPTIONS[0],
      dates: [{
        date: '2026-10-02', day_of_week: 5,
        slots: [{
          pickup_slot_id: 40, start_time: '06:00', end_time: '09:00',
          cutoff_at: '2026-09-20T18:00:00+07:00', is_bookable: true,
        }],
      }],
    }]));
    fillCart();
    renderAt('/customer/checkout');

    
    const slot = await screen.findByRole('radio', { name: /06:00\u201309:00/ });
    expect(slot).toBeDisabled();
    expect(screen.getByTitle(/pre-order cutoff has passed/i)).toBeInTheDocument();
  });

  it('sends exactly the body CU-04 declares, with an idempotency key', async () => {
    mock.onPost('/customer/orders/').reply(201, ok({ orders: [PLACED_ORDER] }));
    fillCart();
    renderAt('/customer/checkout');
    await chooseSlots();

    await userEvent.type(screen.getByLabelText(/note for green stall/i), 'Please pick young greens');
    await userEvent.click(screen.getByRole('button', { name: /confirm 2 orders/i }));
    await userEvent.click(await screen.findByRole('button', { name: /^place 2 orders$/i }));

    await waitFor(() => expect(mock.history.post).toHaveLength(1));
    const request = mock.history.post[0];
    expect(request.headers['Idempotency-Key']).toMatch(/^[0-9a-f-]{36}$/);
    expect(JSON.parse(request.data)).toEqual({
      groups: [
        {
          farmer_id: 9,
          pickup_slot_id: 40,
          pickup_date: '2026-10-02',
          note: 'Please pick young greens',
          items: [{ product_id: 4, quantity: 2 }],
        },
        {
          farmer_id: 11,
          pickup_slot_id: 55,
          pickup_date: '2026-10-03',
          items: [{ product_id: 7, quantity: 3 }],
        },
      ],
    });
  });

  it('tells the customer stock is only held once the farmer accepts (D-029)', async () => {
    fillCart();
    renderAt('/customer/checkout');

    expect(await screen.findByText(/stock is reserved only when the farmer accepts your order/i))
      .toBeInTheDocument();
  });

  it('puts a shortage back on the line it belongs to', async () => {
    mock.onPost('/customer/orders/').reply(400, failed({
      message: 'Some products do not have enough stock',
      code: 'INSUFFICIENT_STOCK',
      errors: { 'groups.0.items.0.quantity': ['Only 1 kg left'] },
      data: { available: { 4: 1 } },
    }));
    fillCart();
    renderAt('/customer/checkout');
    await chooseSlots();
    await userEvent.click(screen.getByRole('button', { name: /confirm 2 orders/i }));
    await userEvent.click(await screen.findByRole('button', { name: /^place 2 orders$/i }));

    const lettuce = await screen.findByRole('listitem', { name: /da lat lettuce/i });
    expect(within(lettuce).getByText('Only 1 kg left')).toBeInTheDocument();
    
    expect(useCartStore.getState().lines).toHaveLength(2);
  });

  it('explains the open order limit in its own dialog (D-005)', async () => {
    const message = 'You have 10 orders waiting for farmer confirmation. '
      + 'Please wait for them to be confirmed before placing more.';
    mock.onPost('/customer/orders/').reply(422, failed({
      message, code: 'OPEN_ORDER_LIMIT_EXCEEDED', errors: { non_field_errors: [message] },
    }));
    fillCart();
    renderAt('/customer/checkout');
    await chooseSlots();
    await userEvent.click(screen.getByRole('button', { name: /confirm 2 orders/i }));
    await userEvent.click(await screen.findByRole('button', { name: /^place 2 orders$/i }));

    expect(await screen.findByText(/10 orders waiting for farmer confirmation/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /my orders/i })).toHaveAttribute('href', '/customer/orders');
  });

  
  it('empties the cart once the orders exist', async () => {
    mock.onPost('/customer/orders/').reply(201, ok({ orders: [PLACED_ORDER] }));
    fillCart();
    renderAt('/customer/checkout');
    await chooseSlots();
    await userEvent.click(screen.getByRole('button', { name: /confirm 2 orders/i }));
    await userEvent.click(await screen.findByRole('button', { name: /^place 2 orders$/i }));

    await waitFor(() => expect(useCartStore.getState().lines).toHaveLength(0));
  });
});

describe('CheckoutSuccessPage (C-03)', () => {
  it('lists what was just created and where to go next', () => {
    renderAt('/customer/checkout/success', null, { orders: [PLACED_ORDER] });

    expect(screen.getByText(/1 order placed successfully/i)).toBeInTheDocument();
    expect(screen.getByText('Green Stall')).toBeInTheDocument();
    expect(screen.getByText('$25.00')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /view my orders/i })).toHaveAttribute('href', '/customer/orders');
    expect(screen.getByRole('link', { name: /continue shopping/i })).toHaveAttribute('href', '/products');
  });

  it('falls back to the order list when the page is opened on its own', () => {
    
    renderAt('/customer/checkout/success');

    expect(screen.getByRole('link', { name: /view my orders/i })).toBeInTheDocument();
    expect(screen.queryByText(/placed successfully/i)).not.toBeInTheDocument();
  });
});
