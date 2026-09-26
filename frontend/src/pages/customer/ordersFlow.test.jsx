import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import MockAdapter from 'axios-mock-adapter';
import axiosClient from '../../lib/axiosClient';
import { useAuthStore } from '../../stores/auth.store';
import { useCartStore } from '../../stores/cart.store';
import OrdersPage from './OrdersPage';
import OrderDetailPage from './OrderDetailPage';
import EditOrderPage from './EditOrderPage';
import ReviewOrderPage from './ReviewOrderPage';

const toast = { success: vi.fn(), error: vi.fn(), message: vi.fn() };
vi.mock('sonner', () => ({ toast: { success: (...a) => toast.success(...a), error: (...a) => toast.error(...a), message: (...a) => toast.message(...a) } }));

const ok = (data) => ({ success: true, message: 'OK', data, errors: {} });
const failed = ({ message, errors = {}, code, data = {} }) => ({ success: false, message, data, errors, code });
const paged = (results) => ok({
  count: results.length, page: 1, page_size: 20, total_pages: 1, next: null, previous: null, results,
});


const SUMMARY = {
  id: 31, status: 'ACCEPTED', is_overdue: false, is_expiring_soon: false, has_pending_change: false, version: 3,
  customer: { id: 4, full_name: 'Alice Nguyen', phone: '0912345678' },
  farmer: { id: 9, stall_name: 'Green Stall', phone: '0987654321' },
  market: { id: 2, name: 'Ben Thanh Market', address: '1 Le Loi Street', latitude: 10.772345, longitude: 106.698765 },
  stall_label: 'Row B, Stall 12',
  pickup_date: '2026-10-02',
  pickup_start_at: '2026-10-02T06:00:00+07:00',
  pickup_end_at: '2026-10-02T09:00:00+07:00',
  cutoff_at: '2026-10-01T18:00:00+07:00',
  item_count: 2, total_amount: '25.00', created_at: '2026-09-26T08:00:00+07:00',
};


const DETAIL = {
  ...SUMMARY,
  pickup_slot_id: 40,
  note: 'Please pick young greens',
  items: [
    {
      id: 71, product_id: 4, product_name: 'Da Lat lettuce', unit: 'kg',
      unit_price: '12.50', quantity: 2, line_total: '25.00', product_image: null,
    },
  ],
  status_history: [
    {
      from_status: null, to_status: 'PLACED', transition: 'T1', actor_role: 'CUSTOMER',
      actor_name: 'Alice Nguyen', change_reason: null, created_at: '2026-09-26T08:00:00+07:00',
    },
    {
      from_status: 'PLACED', to_status: 'ACCEPTED', transition: 'T2', actor_role: 'FARMER',
      actor_name: 'Green Stall', change_reason: null, created_at: '2026-09-26T09:00:00+07:00',
    },
  ],
  pending_change: null,
  allowed_actions: ['REQUEST_CHANGE', 'CANCEL'],
  review_state: null,
};

const COMPLETED = {
  ...DETAIL,
  status: 'COMPLETED',
  version: 6,
  allowed_actions: ['REVIEW', 'REORDER'],
  review_state: { farmer_reviewed: false, items_pending_review: [71] },
  status_history: [
    ...DETAIL.status_history,
    {
      from_status: 'READY_FOR_PICKUP', to_status: 'COMPLETED', transition: 'T10', actor_role: 'FARMER',
      actor_name: 'Green Stall', change_reason: null, created_at: '2026-10-02T07:00:00+07:00',
    },
  ],
};

const PICKUP_OPTIONS = [{
  market_id: 2, market_name: 'Ben Thanh Market', stall_label: 'Row B, Stall 12',
  latitude: 10.772345, longitude: 106.698765,
  dates: [{
    date: '2026-10-03', day_of_week: 6,
    slots: [
      { pickup_slot_id: 41, start_time: '15:00', end_time: '18:00', cutoff_at: '2026-10-02T18:00:00+07:00', is_bookable: true },
    ],
  }],
}];

let mock;

beforeEach(() => {
  mock = new MockAdapter(axiosClient);
  useAuthStore.getState().setTokens({ access: 'a', refresh: 'r', role: 'CUSTOMER' });
  useCartStore.getState().clear();
  toast.success.mockClear();
  toast.error.mockClear();
  toast.message.mockClear();
});

afterEach(() => {
  mock.restore();
  useCartStore.getState().clear();
  useAuthStore.getState().clearSession();
});

function renderAt(path) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/customer/orders" element={<OrdersPage />} />
          <Route path="/customer/orders/:orderId" element={<OrderDetailPage />} />
          <Route path="/customer/orders/:orderId/edit" element={<EditOrderPage />} />
          <Route path="/customer/orders/:orderId/review" element={<ReviewOrderPage />} />
          <Route path="/customer/cart" element={<p>Cart page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function lastGet() {
  return mock.history.get.at(-1);
}

describe('OrdersPage (C-04)', () => {
  it('opens on the orders still running', async () => {
    mock.onGet('/customer/orders/').reply(200, paged([SUMMARY]));
    renderAt('/customer/orders');

    await waitFor(() => expect(mock.history.get).toHaveLength(1));
    
    expect(lastGet().params).toMatchObject({ tab: 'open' });
    expect(await screen.findByRole('link', { name: /#31/ })).toBeInTheDocument();
    expect(screen.getByText('Green Stall')).toBeInTheDocument();
    expect(screen.getByText(/ben thanh market/i)).toBeInTheDocument();
  });

  it('asks for the finished orders when the history tab is opened', async () => {
    mock.onGet('/customer/orders/').reply(200, paged([{ ...SUMMARY, status: 'COMPLETED' }]));
    renderAt('/customer/orders');
    await screen.findByRole('link', { name: /#31/ });

    await userEvent.click(screen.getByRole('tab', { name: /history/i }));

    await waitFor(() => expect(lastGet().params).toMatchObject({ tab: 'history' }));
  });

  it('narrows the list by status without inventing a filter the server has no name for', async () => {
    mock.onGet('/customer/orders/').reply(200, paged([SUMMARY]));
    renderAt('/customer/orders');
    await screen.findByRole('link', { name: /#31/ });

    await userEvent.click(screen.getByRole('checkbox', { name: /accepted/i }));

    
    await waitFor(() => expect(lastGet().params).toMatchObject({ tab: 'open', status: 'ACCEPTED' }));
  });

  it('counts down to the moment the order stops being editable', async () => {
    mock.onGet('/customer/orders/').reply(200, paged([SUMMARY]));
    renderAt('/customer/orders');

    expect(await screen.findByText(/edit\/cancel until/i)).toBeInTheDocument();
  });

  it('says so when a tab has nothing in it', async () => {
    mock.onGet('/customer/orders/').reply(200, paged([]));
    renderAt('/customer/orders');

    expect(await screen.findByText(/no orders here yet/i)).toBeInTheDocument();
  });
});

describe('OrderDetailPage (C-05)', () => {
  it('shows the lines with the price that was snapshotted at checkout', async () => {
    mock.onGet('/customer/orders/31/').reply(200, ok(DETAIL));
    renderAt('/customer/orders/31');

    const items = await screen.findByRole('table', { name: /items/i });
    expect(within(items).getByText('Da Lat lettuce')).toBeInTheDocument();
    expect(within(items).getByText('$12.50')).toBeInTheDocument();
    expect(within(items).getByText('$25.00')).toBeInTheDocument();
    expect(screen.getByText(/pay on pickup/i)).toBeInTheDocument();
  });

  it('gives the stall a phone number that can be dialled (D-026)', async () => {
    mock.onGet('/customer/orders/31/').reply(200, ok(DETAIL));
    renderAt('/customer/orders/31');

    expect(await screen.findByRole('link', { name: /call/i })).toHaveAttribute('href', 'tel:0987654321');
    expect(screen.getByRole('link', { name: /directions/i })).toHaveAttribute(
      'href',
      'https://www.google.com/maps/dir/?api=1&destination=10.772345,106.698765',
    );
  });

  it('renders only the actions the server allows', async () => {
    mock.onGet('/customer/orders/31/').reply(200, ok(DETAIL));
    renderAt('/customer/orders/31');

    expect(await screen.findByRole('link', { name: /request a change/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /cancel order/i })).toBeInTheDocument();
    
    expect(screen.queryByRole('button', { name: /reorder/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /review/i })).not.toBeInTheDocument();
  });

  it('walks through the trail naming who acted, and hides the ones D-033 keeps anonymous', async () => {
    mock.onGet('/customer/orders/31/').reply(200, ok({
      ...DETAIL,
      status: 'CANCELLED',
      allowed_actions: ['REORDER'],
      status_history: [
        ...DETAIL.status_history,
        {
          from_status: 'ACCEPTED', to_status: 'CANCELLED', transition: 'T13', actor_role: 'ADMIN',
          actor_name: null, change_reason: 'The order was closed because the account was locked.',
          created_at: '2026-09-27T10:00:00+07:00',
        },
      ],
    }));
    renderAt('/customer/orders/31');

    const trail = await screen.findByRole('list', { name: /history/i });
    expect(within(trail).getByText('Green Stall')).toBeInTheDocument();
    expect(within(trail).getByText(/account was locked/i)).toBeInTheDocument();
    expect(within(trail).getByText(/system/i)).toBeInTheDocument();
  });

  it('cancels with the version it was showing, so a stale tab cannot win', async () => {
    mock.onGet('/customer/orders/31/').reply(200, ok(DETAIL));
    mock.onPost('/customer/orders/31/cancel/').reply(200, ok({ ...DETAIL, status: 'CANCELLED', version: 4 }));
    renderAt('/customer/orders/31');
    await userEvent.click(await screen.findByRole('button', { name: /cancel order/i }));

    await userEvent.type(screen.getByLabelText(/reason/i), 'Plans changed');
    await userEvent.click(screen.getByRole('button', { name: /^cancel order$/i, hidden: false }));

    await waitFor(() => expect(mock.history.post).toHaveLength(1));
    expect(mock.history.post[0].headers['If-Match']).toBe('3');
    expect(JSON.parse(mock.history.post[0].data)).toEqual({ reason: 'Plans changed' });
  });

  it('asks the customer to reload when someone else moved the order first (409)', async () => {
    mock.onGet('/customer/orders/31/').reply(200, ok(DETAIL));
    mock.onPost('/customer/orders/31/cancel/').reply(409, failed({
      message: 'This order was updated by someone else', code: 'RESOURCE_MODIFIED',
    }));
    renderAt('/customer/orders/31');
    await userEvent.click(await screen.findByRole('button', { name: /cancel order/i }));
    await userEvent.click(screen.getByRole('button', { name: /^cancel order$/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/updated/i);
  });

  it('compares the change request with what the order holds today (D-030)', async () => {
    mock.onGet('/customer/orders/31/').reply(200, ok({
      ...DETAIL,
      has_pending_change: true,
      pending_change: {
        items: [{
          product_id: 4, product_name: 'Da Lat lettuce', unit: 'kg',
          quantity: 5, current_quantity: 2, stock_available: 20, unit_price: '12.50',
        }],
        pickup_slot_id: 41, pickup_date: '2026-10-03',
        pickup_start_at: '2026-10-03T15:00:00+07:00', pickup_end_at: '2026-10-03T18:00:00+07:00',
        cutoff_at: '2026-10-02T18:00:00+07:00', note: 'More greens please',
        estimated_total: '62.50', requested_at: '2026-09-26T10:00:00+07:00',
        expires_at: '2026-10-02T06:00:00+07:00',
      },
    }));
    renderAt('/customer/orders/31');

    const panel = await screen.findByRole('region', { name: /change request/i });
    expect(within(panel).getByText(/waiting for the farmer/i)).toBeInTheDocument();
    expect(within(panel).getByText(/2 → 5/)).toBeInTheDocument();
    expect(within(panel).getByText('$62.50')).toBeInTheDocument();
  });

  it('puts a finished order back in the cart at today’s prices, saying what it left out', async () => {
    mock.onGet('/customer/orders/31/').reply(200, ok({ ...COMPLETED, review_state: { farmer_reviewed: true, items_pending_review: [] }, allowed_actions: ['REORDER'] }));
    mock.onGet('/customer/orders/31/reorder-preview/').reply(200, ok({
      items: [{
        product: {
          id: 4, name: 'Da Lat lettuce', image: null, price: '13.00', unit: 'kg', stock_quantity: 10,
          is_available: true, availability: 'IN_STOCK', category: { id: 1, name: 'Vegetables' },
          farmer: { id: 9, stall_name: 'Green Stall' }, rating_avg: null, rating_count: 0, is_favorite: false,
        },
        quantity: 2,
      }],
      skipped: [{ product_id: 5, product_name: 'Tomato', reason: 'OUT_OF_STOCK' }],
    }));
    renderAt('/customer/orders/31');

    await userEvent.click(await screen.findByRole('button', { name: /reorder/i }));

    await waitFor(() => expect(useCartStore.getState().lines).toEqual([{
      product_id: 4, farmer_id: 9, farmer_stall_name: 'Green Stall', name: 'Da Lat lettuce',
      unit: 'kg', price: '13.00', image: null, quantity: 2,
    }]));
    expect(toast.message).toHaveBeenCalledWith(expect.stringMatching(/tomato/i));
  });
});

describe('EditOrderPage (C-06)', () => {
  it('sends the full list of items, not the difference (CU-07)', async () => {
    mock.onGet('/customer/orders/31/').reply(200, ok({ ...DETAIL, status: 'PLACED', allowed_actions: ['MODIFY', 'CANCEL'] }));
    mock.onGet('/public/farmers/9/pickup-options/').reply(200, ok(PICKUP_OPTIONS));
    mock.onPatch('/customer/orders/31/').reply(200, ok({ ...DETAIL, status: 'PLACED', version: 4 }));
    renderAt('/customer/orders/31/edit');

    await userEvent.click(await screen.findByRole('button', { name: /increase quantity/i }));
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => expect(mock.history.patch).toHaveLength(1));
    expect(mock.history.patch[0].headers['If-Match']).toBe('3');
    expect(JSON.parse(mock.history.patch[0].data)).toEqual({
      items: [{ product_id: 4, quantity: 3 }],
      note: 'Please pick young greens',
    });
  });

  it('sends a reschedule as both fields together, or not at all', async () => {
    mock.onGet('/customer/orders/31/').reply(200, ok({ ...DETAIL, status: 'PLACED', allowed_actions: ['MODIFY', 'CANCEL'] }));
    mock.onGet('/public/farmers/9/pickup-options/').reply(200, ok(PICKUP_OPTIONS));
    mock.onPatch('/customer/orders/31/').reply(200, ok({ ...DETAIL, status: 'PLACED', version: 4 }));
    renderAt('/customer/orders/31/edit');

    await userEvent.click(await screen.findByRole('radio', { name: /15:00–18:00/ }));
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => expect(mock.history.patch).toHaveLength(1));
    const body = JSON.parse(mock.history.patch[0].data);
    
    expect(body.pickup_slot_id).toBe(41);
    expect(body.pickup_date).toBe('2026-10-03');
  });

  it('warns that an accepted order only gets a change request (D-030)', async () => {
    mock.onGet('/customer/orders/31/').reply(200, ok(DETAIL));
    mock.onGet('/public/farmers/9/pickup-options/').reply(200, ok(PICKUP_OPTIONS));
    renderAt('/customer/orders/31/edit');

    expect(await screen.findByText(/sent to the farmer for approval/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /send change request/i })).toBeInTheDocument();
  });

  it('refuses to empty the order here, pointing at cancel instead', async () => {
    mock.onGet('/customer/orders/31/').reply(200, ok({ ...DETAIL, status: 'PLACED', allowed_actions: ['MODIFY', 'CANCEL'] }));
    mock.onGet('/public/farmers/9/pickup-options/').reply(200, ok(PICKUP_OPTIONS));
    renderAt('/customer/orders/31/edit');

    await userEvent.click(await screen.findByRole('button', { name: /remove da lat lettuce/i }));

    expect(screen.getByText(/at least one item/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /save changes/i })).toBeDisabled();
    expect(mock.history.patch).toHaveLength(0);
  });

  it('puts a shortage from CU-07 on the line it belongs to', async () => {
    mock.onGet('/customer/orders/31/').reply(200, ok({ ...DETAIL, status: 'PLACED', allowed_actions: ['MODIFY', 'CANCEL'] }));
    mock.onGet('/public/farmers/9/pickup-options/').reply(200, ok(PICKUP_OPTIONS));
    mock.onPatch('/customer/orders/31/').reply(400, failed({
      message: 'Some products do not have enough stock',
      code: 'INSUFFICIENT_STOCK',
      errors: { 'items.0.quantity': ['Only 2 kg left'] },
    }));
    renderAt('/customer/orders/31/edit');
    await userEvent.click(await screen.findByRole('button', { name: /increase quantity/i }));
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }));

    const line = await screen.findByRole('listitem', { name: /da lat lettuce/i });
    expect(within(line).getByText('Only 2 kg left')).toBeInTheDocument();
  });
});

describe('ReviewOrderPage (C-07)', () => {
  it('asks about the stall and each item that has no review yet', async () => {
    mock.onGet('/customer/orders/31/').reply(200, ok(COMPLETED));
    renderAt('/customer/orders/31/review');

    expect(await screen.findByRole('region', { name: /green stall/i })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: /da lat lettuce/i })).toBeInTheDocument();
  });

  it('leaves out what was already reviewed', async () => {
    mock.onGet('/customer/orders/31/').reply(200, ok({
      ...COMPLETED,
      review_state: { farmer_reviewed: true, items_pending_review: [] },
    }));
    renderAt('/customer/orders/31/review');

    expect(await screen.findByText(/already been reviewed/i)).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: /green stall/i })).not.toBeInTheDocument();
  });

  it('posts the stall review to CU-10', async () => {
    mock.onGet('/customer/orders/31/').reply(200, ok(COMPLETED));
    mock.onPost('/customer/orders/31/farmer-review/').reply(201, ok({
      id: 1, type: 'FARMER', rating: 5, comment: 'Great greens', customer_display_name: 'Alice N.',
      product: null, reply: null, replied_at: null, created_at: '2026-10-03T08:00:00+07:00',
    }));
    renderAt('/customer/orders/31/review');
    const stall = await screen.findByRole('region', { name: /green stall/i });

    await userEvent.click(within(stall).getByRole('radio', { name: /5 stars/i }));
    await userEvent.type(within(stall).getByRole('textbox'), 'Great greens');
    await userEvent.click(within(stall).getByRole('button', { name: /submit/i }));

    await waitFor(() => expect(mock.history.post).toHaveLength(1));
    expect(mock.history.post[0].url).toBe('/customer/orders/31/farmer-review/');
    expect(JSON.parse(mock.history.post[0].data)).toEqual({ rating: 5, comment: 'Great greens' });
  });

  it('posts an item review to CU-11 by its order item id', async () => {
    mock.onGet('/customer/orders/31/').reply(200, ok(COMPLETED));
    mock.onPost('/customer/orders/31/items/71/review/').reply(201, ok({
      id: 2, type: 'PRODUCT', rating: 4, comment: null, customer_display_name: 'Alice N.',
      product: { id: 4, name: 'Da Lat lettuce' }, reply: null, replied_at: null,
      created_at: '2026-10-03T08:00:00+07:00',
    }));
    renderAt('/customer/orders/31/review');
    const item = await screen.findByRole('region', { name: /da lat lettuce/i });

    await userEvent.click(within(item).getByRole('radio', { name: /4 stars/i }));
    await userEvent.click(within(item).getByRole('button', { name: /submit/i }));

    await waitFor(() => expect(mock.history.post).toHaveLength(1));
    expect(mock.history.post[0].url).toBe('/customer/orders/31/items/71/review/');
    expect(JSON.parse(mock.history.post[0].data)).toEqual({ rating: 4, comment: null });
  });

  it('will not submit a review with no rating', async () => {
    mock.onGet('/customer/orders/31/').reply(200, ok(COMPLETED));
    renderAt('/customer/orders/31/review');
    const stall = await screen.findByRole('region', { name: /green stall/i });

    expect(within(stall).getByRole('button', { name: /submit/i })).toBeDisabled();
    expect(mock.history.post).toHaveLength(0);
  });

  it('explains a refusal from the server instead of pretending it worked', async () => {
    mock.onGet('/customer/orders/31/').reply(200, ok(COMPLETED));
    mock.onPost('/customer/orders/31/farmer-review/').reply(422, failed({
      message: 'This order cannot be reviewed', code: 'REVIEW_NOT_ALLOWED',
    }));
    renderAt('/customer/orders/31/review');
    const stall = await screen.findByRole('region', { name: /green stall/i });

    await userEvent.click(within(stall).getByRole('radio', { name: /5 stars/i }));
    await userEvent.click(within(stall).getByRole('button', { name: /submit/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/cannot be reviewed/i);
  });
});
