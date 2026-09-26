import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import axiosClient from '../../lib/axiosClient';
import { authApi } from './authApi';
import { DASHBOARD_PATH } from '../../constants';


const ME = {
  success: true, message: 'OK', errors: {},
  data: { id: 4, email: 'alice@example.com', role: 'CUSTOMER', display_name: 'Alice Nguyen', farmer_status: null },
};
const TOKENS = (user) => ({
  success: true, message: 'OK', errors: {},
  data: { access: 'access-1', refresh: 'refresh-1', user },
});

let mock;

beforeEach(() => {
  mock = new MockAdapter(axiosClient);
});

afterEach(() => {
  mock.restore();
});

describe('endpoints match the API contract', () => {
  it('AU-03 signs in at the customer and farmer portal', async () => {
    mock.onPost('/auth/login/').reply(200, TOKENS(ME.data));

    const result = await authApi.login({ email: 'alice@example.com', password: 'Mango2026x' });

    expect(mock.history.post[0].url).toBe('/auth/login/');
    expect(result.access).toBe('access-1');
    expect(result.user.role).toBe('CUSTOMER');
  });

  it('AU-09 signs in at the separate admin portal (D-027)', async () => {
    mock.onPost('/auth/admin/login/').reply(200, TOKENS({ ...ME.data, role: 'ADMIN', display_name: 'Administrator' }));

    await authApi.adminLogin({ email: 'admin@example.com', password: 'Mango2026x' });

    expect(mock.history.post[0].url).toBe('/auth/admin/login/');
  });

  it('AU-05 logs out with the refresh token, not the access token', async () => {
    
    mock.onPost('/auth/logout/').reply(204);

    await authApi.logout({ refresh: 'refresh-1' });

    expect(JSON.parse(mock.history.post[0].data)).toEqual({ refresh: 'refresh-1' });
  });

  it('AU-06 reads the signed-in account in one call', async () => {
    mock.onGet('/auth/me/').reply(200, ME);

    const me = await authApi.me();

    expect(mock.history.get.map((call) => call.url)).toEqual(['/auth/me/']);
    expect(me.display_name).toBe('Alice Nguyen');
  });

  it('AU-06 takes farmer_status straight from /auth/me/ without a second request', async () => {
    
    mock.onGet('/auth/me/').reply(200, {
      ...ME,
      data: { ...ME.data, role: 'FARMER', display_name: 'Green Stall', farmer_status: 'PENDING' },
    });

    const me = await authApi.me();

    expect(me.farmer_status).toBe('PENDING');
    expect(mock.history.get).toHaveLength(1);
  });

  it('never reaches for an endpoint the backend does not have', async () => {
    
    mock.onGet('/auth/me/').reply(200, {
      ...ME,
      data: { ...ME.data, role: 'FARMER', display_name: 'Green Stall', farmer_status: null },
    });

    const me = await authApi.me();

    expect(mock.history.get.map((call) => call.url)).toEqual(['/auth/me/']);
    expect(me.farmer_status).toBeNull();
  });

  it('AU-07 sends confirm_password, which the serializer requires', async () => {
    
    mock.onPost('/auth/change-password/').reply(200, { success: true, message: 'OK', data: {}, errors: {} });
    const body = {
      current_password: 'Mango2026x', new_password: 'Papaya2027z', confirm_password: 'Papaya2027z',
    };

    await authApi.changePassword(body);

    expect(JSON.parse(mock.history.post[0].data)).toEqual(body);
  });

  it('AU-01 and AU-02 register and sign the account in', async () => {
    mock.onPost('/auth/register/customer/').reply(201, TOKENS(ME.data));
    mock.onPost('/auth/register/farmer/').reply(201, TOKENS({ ...ME.data, role: 'FARMER', farmer_status: 'PENDING' }));

    const customer = await authApi.registerCustomer({ email: 'a@b.co', password: 'x', confirm_password: 'x' });
    const farmer = await authApi.registerFarmer({ email: 'c@d.co', password: 'x', confirm_password: 'x' });

    expect(customer.user.role).toBe('CUSTOMER');
    expect(farmer.user.farmer_status).toBe('PENDING');
    
    expect(JSON.parse(mock.history.post[0].data).confirm_password).toBe('x');
    expect(JSON.parse(mock.history.post[1].data).confirm_password).toBe('x');
    expect(mock.history.post.map((call) => call.url)).toEqual([
      '/auth/register/customer/', '/auth/register/farmer/',
    ]);
  });

  it('AU-08 asks for a one-time WebSocket ticket', async () => {
    mock.onPost('/auth/ws-ticket/').reply(200, {
      success: true, message: 'OK', data: { ticket: 'abc', expires_in: 30 }, errors: {},
    });

    const ticket = await authApi.wsTicket();

    expect([mock.history.post[0].url, ticket.expires_in]).toEqual(['/auth/ws-ticket/', 30]);
  });
});

describe('where each role lands after signing in', () => {
  it('points every role at the dashboard route of Pass 3', () => {
    
    expect(DASHBOARD_PATH).toEqual({ CUSTOMER: '/customer', FARMER: '/farmer', ADMIN: '/admin' });
  });
});
