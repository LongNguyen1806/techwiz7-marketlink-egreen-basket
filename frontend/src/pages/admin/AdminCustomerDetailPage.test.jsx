import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AdminCustomerDetailPage from './AdminCustomerDetailPage';
import { adminApi } from '../../api/admin/adminApi';
import { renderPage } from '../../test/render';

vi.mock('../../api/admin/adminApi', () => ({
  adminApi: {
    getCustomer: vi.fn(),
    updateCustomer: vi.fn(),
    getChangeLog: vi.fn(),
  },
}));

const CUSTOMER = {
  id: 2703,
  email: 'shopper99@demo.marketlink.local',
  full_name: 'Dinh Minh Tam',
  phone: '0900000099',
  address: '405 Quang Trung, District 3',
  date_joined: '2026-09-27T15:37:00+07:00',
  is_active: true,
  deactivation_reason: null,
  total_orders: 2,
  open_orders: 1,
  no_show_count: 0,
  at_risk: false,
  recent_orders: [],
  auto_lock: null,
};

function show(customer) {
  adminApi.getCustomer.mockResolvedValue(customer);
  return renderPage(<AdminCustomerDetailPage />, {
    route: `/admin/customers/${customer.id}`,
    path: '/admin/customers/:id',
  });
}

describe('customer detail', () => {
  beforeEach(() => {
    adminApi.getChangeLog.mockResolvedValue([]);
  });

  it('shows an empty change history instead of an error', async () => {
    show(CUSTOMER);

    expect(await screen.findByText('No changes recorded yet.')).toBeInTheDocument();
    expect(adminApi.getChangeLog).toHaveBeenCalledWith('customer_profile', 2703);
  });

  it('lists the missed orders behind an automatic lock', async () => {
    show({
      ...CUSTOMER,
      is_active: false,
      no_show_count: 3,
      deactivation_reason: 'Auto-locked: did not collect orders #1, #2, #3 within 30 days.',
      auto_lock: {
        locked_at: '2026-09-28T08:00:00+07:00',
        orders: [1, 2, 3].map((id) => ({
          id,
          stall_name: 'Green Farm',
          market_name: 'Cho Ba Chieu',
          pickup_date: '2026-09-2' + id,
          total_amount: '25.00',
        })),
      },
    });

    expect(await screen.findByText('Locked automatically')).toBeInTheDocument();
    for (const id of [1, 2, 3]) {
      expect(screen.getByRole('link', { name: `#${id}` })).toHaveAttribute('href', `/admin/orders?q=${id}`);
    }
  });

  it('has no automatic-lock box for an account the system did not lock', async () => {
    show(CUSTOMER);

    await screen.findByText('Dinh Minh Tam');
    expect(screen.queryByText('Locked automatically')).not.toBeInTheDocument();
  });
});
