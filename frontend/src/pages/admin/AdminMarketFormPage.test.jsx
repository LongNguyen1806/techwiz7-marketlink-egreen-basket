import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AdminMarketFormPage from './AdminMarketFormPage';
import { adminApi } from '../../api/admin/adminApi';
import { renderPage } from '../../test/render';

vi.mock('../../api/admin/adminApi', () => ({
  adminApi: {
    getMarket: vi.fn(),
    updateMarket: vi.fn(),
    createMarket: vi.fn(),
    previewMarketUpdate: vi.fn(),
    geocodeAddress: vi.fn(),
    getMarketClosures: vi.fn(),
  },
}));

// Leaflet needs a real browser layout; the form logic does not.
const flyTo = vi.fn();
vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }) => <div data-testid="map">{children}</div>,
  TileLayer: () => null,
  Marker: () => null,
  useMap: () => ({ flyTo }),
  useMapEvents: () => null,
}));

const MARKET = {
  id: 143,
  name: 'Cho Ba Chieu',
  address: 'Le Quang Dinh, Binh Thanh',
  description: '',
  image: null,
  latitude: 10.8,
  longitude: 106.7,
  open_time: '05:30',
  close_time: '12:00',
  operating_days: [1, 2, 3],
};

const NO_IMPACT = {
  changed_fields: ['description'],
  location_changed: false,
  schedule_changed: false,
  orders_to_reschedule: 0,
  slots_to_disable: 0,
  customers_to_notify: 0,
  stalls_to_notify: 0,
};

function edit() {
  return renderPage(<AdminMarketFormPage />, {
    route: '/admin/markets/143/edit',
    path: '/admin/markets/:id/edit',
  });
}

describe('market form', () => {
  beforeEach(() => {
    adminApi.getMarket.mockResolvedValue(MARKET);
    adminApi.getMarketClosures.mockResolvedValue([]);
    adminApi.updateMarket.mockResolvedValue({ ...MARKET, orders_to_reschedule: 0, notified: 0 });
  });

  it('saves straight away when the edit reaches nobody', async () => {
    adminApi.previewMarketUpdate.mockResolvedValue(NO_IMPACT);
    edit();
    await screen.findByDisplayValue('Cho Ba Chieu');

    await userEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(adminApi.updateMarket).toHaveBeenCalled());
    const [, payload] = adminApi.updateMarket.mock.calls[0];
    // The photo URL is never sent back into the file field.
    expect(payload).not.toHaveProperty('image');
  });

  it('shows who a schedule change reaches and wants the word typed first', async () => {
    adminApi.previewMarketUpdate.mockResolvedValue({
      ...NO_IMPACT,
      schedule_changed: true,
      orders_to_reschedule: 2,
      slots_to_disable: 1,
      customers_to_notify: 2,
      stalls_to_notify: 1,
    });
    edit();
    await screen.findByDisplayValue('Cho Ba Chieu');

    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/choose a new pickup/)).toBeInTheDocument();
    const confirm = within(dialog).getByRole('button', { name: 'Save and notify' });
    expect(confirm).toBeDisabled();

    await userEvent.type(within(dialog).getByLabelText(/Type confirm/), 'confirm');
    await userEvent.click(confirm);

    await waitFor(() => expect(adminApi.updateMarket).toHaveBeenCalled());
    const [id, payload] = adminApi.updateMarket.mock.calls[0];
    expect(id).toBe(143);
    expect(payload.confirm_affected_orders).toBe(true);
  });

  it('pins the address it finds and moves the map there', async () => {
    adminApi.geocodeAddress.mockResolvedValue({ found: true, latitude: 10.8123456789, longitude: 106.7 });
    edit();
    await screen.findByDisplayValue('Cho Ba Chieu');

    await userEvent.click(screen.getByRole('button', { name: 'Find on map' }));

    expect(await screen.findByText(/Pinned from the address/)).toBeInTheDocument();
    expect(adminApi.geocodeAddress).toHaveBeenCalledWith('Le Quang Dinh, Binh Thanh');
    // The view flies to the spot found; the form keeps it rounded to six decimals.
    expect(flyTo).toHaveBeenCalledWith([10.8123456789, 106.7], 17);
  });

  it('keeps the old pin and says so when the address is not found', async () => {
    adminApi.geocodeAddress.mockResolvedValue({ found: false, latitude: null, longitude: null });
    edit();
    await screen.findByDisplayValue('Cho Ba Chieu');

    await userEvent.click(screen.getByRole('button', { name: 'Find on map' }));

    expect(await screen.findByText(/Couldn't find this address/)).toBeInTheDocument();
    expect(flyTo).not.toHaveBeenCalled();
  });
});
