import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import AdminMarketDetailPage from './AdminMarketDetailPage';
import { adminApi } from '../../api/admin/adminApi';
import { renderPage } from '../../test/render';

vi.mock('../../api/admin/adminApi', () => ({ adminApi: { getMarket: vi.fn() } }));
vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }) => <div data-testid="map">{children}</div>,
  TileLayer: () => null,
  Marker: () => null,
}));

describe('market detail (#4)', () => {
  it('reads the market without any editable field, with a separate Edit button', async () => {
    adminApi.getMarket.mockResolvedValue({
      id: 143,
      name: 'Cho Ba Chieu',
      address: 'Le Quang Dinh, Binh Thanh',
      description: 'Covered hall.',
      latitude: 10.8,
      longitude: 106.7,
      open_time: '05:30',
      close_time: '12:00',
      operating_days: [1, 3],
      farmer_count: 4,
      open_order_count: 2,
      is_active: true,
      upcoming_closures: [{ id: 1, start_date: '2026-09-25', end_date: '2026-09-29', reason: 'Health inspection' }],
    });

    renderPage(<AdminMarketDetailPage />, { route: '/admin/markets/143', path: '/admin/markets/:id' });

    expect(await screen.findByRole('heading', { name: 'Cho Ba Chieu' })).toBeInTheDocument();
    expect(screen.getByText('Mon, Wed')).toBeInTheDocument();
    expect(screen.getByText(/Health inspection/)).toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Edit' })).toHaveAttribute('href', '/admin/markets/143/edit');
  });
});
