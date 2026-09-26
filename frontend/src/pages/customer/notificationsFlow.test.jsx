import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import MockAdapter from 'axios-mock-adapter';
import axiosClient from '../../lib/axiosClient';
import { useAuthStore } from '../../stores/auth.store';
import NotificationsPage from './NotificationsPage';
import { AnnouncementBanner } from '../../components/common/announcements/AnnouncementBanner';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() } }));

const ok = (data) => ({ success: true, message: 'OK', data, errors: {} });
const paged = (results, extra = {}) => ok({
  count: results.length, page: 1, page_size: 20, total_pages: 1, next: null, previous: null,
  results, ...extra,
});

const UNREAD = {
  id: 5, type: 'ORDER_ACCEPTED', title: 'Order accepted',
  message: 'Green Stall accepted order #31', target_url: '/customer/orders/31',
  is_read: false, read_at: null, created_at: '2026-09-26T09:00:00+07:00',
};
const READ = {
  id: 4, type: 'RESTOCK', title: 'Back in stock',
  message: 'Da Lat lettuce is available again', target_url: '/products/4',
  is_read: true, read_at: '2026-09-26T08:30:00+07:00', created_at: '2026-09-25T07:00:00+07:00',
};


const ANNOUNCEMENT = {
  id: 2, title: 'Tet holiday closures', content: 'Several markets are closed from 28/01 to 04/02.',
  audience: 'ALL', starts_at: '2026-09-20T00:00:00+07:00', ends_at: '2026-10-30T00:00:00+07:00',
};

let mock;

beforeEach(() => {
  mock = new MockAdapter(axiosClient);
  mock.onGet('/notifications/unread-count/').reply(200, ok({ unread_count: 1 }));
  useAuthStore.getState().setTokens({ access: 'a', refresh: 'r', role: 'CUSTOMER' });
  localStorage.clear();
});

afterEach(() => {
  mock.restore();
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

function listRequests() {
  return mock.history.get.filter((request) => request.url === '/notifications/');
}

describe('NotificationsPage (C-09)', () => {
  it('lists what arrived, newest first, and says which are unread', async () => {
    mock.onGet('/notifications/').reply(200, paged([UNREAD, READ]));
    renderPage(<NotificationsPage />);

    const rows = await screen.findAllByRole('listitem');
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText('Order accepted')).toBeInTheDocument();
    expect(within(rows[0]).getByText(/accepted order #31/)).toBeInTheDocument();
    
    expect(within(rows[0]).getByRole('button', { name: /mark as read/i })).toBeInTheDocument();
    expect(within(rows[1]).queryByRole('button', { name: /mark as read/i })).not.toBeInTheDocument();
  });

  it('follows the target the backend put on the row', async () => {
    mock.onGet('/notifications/').reply(200, paged([UNREAD]));
    renderPage(<NotificationsPage />);

    expect(await screen.findByRole('link', { name: /order accepted/i }))
      .toHaveAttribute('href', '/customer/orders/31');
  });

  it('asks the server for the unread ones rather than filtering in the browser', async () => {
    mock.onGet('/notifications/').reply(200, paged([UNREAD]));
    renderPage(<NotificationsPage />);
    await screen.findByText('Order accepted');

    await userEvent.click(screen.getByRole('tab', { name: /unread/i }));

    
    
    await waitFor(() => expect(listRequests().at(-1).params).toMatchObject({ is_read: false, page: 1 }));
  });

  it('marks one row read through NO-03 and reloads the list', async () => {
    mock.onGet('/notifications/').reply(200, paged([UNREAD]));
    mock.onPost('/notifications/5/read/').reply(200, ok({ ...UNREAD, is_read: true }));
    renderPage(<NotificationsPage />);
    await screen.findByText('Order accepted');
    const before = listRequests().length;

    await userEvent.click(screen.getByRole('button', { name: /mark as read/i }));

    await waitFor(() => expect(mock.history.post).toHaveLength(1));
    expect(mock.history.post[0].url).toBe('/notifications/5/read/');
    await waitFor(() => expect(listRequests().length).toBeGreaterThan(before));
  });

  it('marks everything read through NO-04', async () => {
    mock.onGet('/notifications/').reply(200, paged([UNREAD]));
    mock.onPost('/notifications/read-all/').reply(200, ok({ updated: 1 }));
    renderPage(<NotificationsPage />);
    await screen.findByText('Order accepted');

    await userEvent.click(screen.getByRole('button', { name: /mark all as read/i }));

    await waitFor(() => expect(mock.history.post.map((request) => request.url))
      .toEqual(['/notifications/read-all/']));
  });

  it('walks through the pages the server reports', async () => {
    mock.onGet('/notifications/').reply(200, paged([UNREAD], { total_pages: 3, next: 2, count: 41 }));
    renderPage(<NotificationsPage />);
    await screen.findByText('Order accepted');

    await userEvent.click(screen.getByRole('button', { name: /next/i }));

    await waitFor(() => expect(listRequests().at(-1).params).toMatchObject({ page: 2 }));
  });

  it('says so when nothing has arrived', async () => {
    mock.onGet('/notifications/').reply(200, paged([]));
    renderPage(<NotificationsPage />);

    expect(await screen.findByText(/no notifications yet/i)).toBeInTheDocument();
  });
});

describe('AnnouncementBanner (N-04)', () => {
  it('shows the notices in force, from PU-13', async () => {
    mock.onGet('/public/announcements/').reply(200, ok([ANNOUNCEMENT]));
    renderPage(<AnnouncementBanner />);

    expect(await screen.findByText('Tet holiday closures')).toBeInTheDocument();
    expect(screen.getByText(/several markets are closed/i)).toBeInTheDocument();
  });

  it('stays out of the way once dismissed, and after a reload', async () => {
    mock.onGet('/public/announcements/').reply(200, ok([ANNOUNCEMENT]));
    const { unmount } = renderPage(<AnnouncementBanner />);
    await screen.findByText('Tet holiday closures');

    await userEvent.click(screen.getByRole('button', { name: /dismiss/i }));

    expect(screen.queryByText('Tet holiday closures')).not.toBeInTheDocument();

    unmount();
    renderPage(<AnnouncementBanner />);

    
    
    
    await waitFor(() => expect(
      mock.history.get.filter((request) => request.url === '/public/announcements/'),
    ).toHaveLength(2));
    expect(screen.queryByText('Tet holiday closures')).not.toBeInTheDocument();
  });

  it('renders nothing at all when there is no notice', async () => {
    mock.onGet('/public/announcements/').reply(200, ok([]));
    const { container } = renderPage(<AnnouncementBanner />);

    await waitFor(() => expect(mock.history.get).toHaveLength(1));
    expect(container).toBeEmptyDOMElement();
  });

  it('does not take the page down when the notices cannot be loaded', async () => {
    mock.onGet('/public/announcements/').reply(500, { success: false, message: 'Boom', data: {}, errors: {} });
    const { container } = renderPage(<AnnouncementBanner />);

    await waitFor(() => expect(mock.history.get).toHaveLength(1));
    expect(container).toBeEmptyDOMElement();
  });
});
