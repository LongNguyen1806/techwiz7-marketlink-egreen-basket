import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import MockAdapter from 'axios-mock-adapter';
import axiosClient from '../../../lib/axiosClient';
import { useAuthStore } from '../../../stores/auth.store';
import { LoginForm } from './LoginForm';
import { RegisterCustomerForm } from './RegisterCustomerForm';
import { RegisterFarmerForm } from './RegisterFarmerForm';
import { ChangePasswordForm } from './ChangePasswordForm';
import AdminLoginPage from '../../../pages/admin/AdminLoginPage';


const navigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal()),
  useNavigate: () => navigate,
}));

const CUSTOMER = {
  id: 4, email: 'alice@example.com', role: 'CUSTOMER', display_name: 'Alice Nguyen', farmer_status: null,
};
const FARMER = {
  id: 9, email: 'stall@example.com', role: 'FARMER', display_name: 'Green Stall', farmer_status: 'PENDING',
};

const ok = (data) => ({ success: true, message: 'OK', data, errors: {} });
const failed = ({ message, errors = {}, code }) => ({ success: false, message, data: {}, errors, code });

let mock;

beforeEach(() => {
  navigate.mockClear();
  mock = new MockAdapter(axiosClient);
  mock.onGet('/auth/me/').reply(200, ok(CUSTOMER));
  useAuthStore.getState().clearSession();
});

afterEach(() => {
  mock.restore();
});

function renderForm(ui) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

function lastPost() {
  const request = mock.history.post.at(-1);
  return { url: request.url, body: JSON.parse(request.data) };
}

async function fillIn(label, value) {
  await userEvent.type(screen.getByLabelText(label), value);
}

describe('LoginForm (G-09)', () => {
  it('sends the email in lower case, as the serializer stores it', async () => {
    mock.onPost('/auth/login/').reply(200, ok({ access: 'a', refresh: 'r', user: CUSTOMER }));
    renderForm(<LoginForm />);

    await fillIn('Email', 'Alice@Example.com');
    await fillIn('Password', 'Mango2026x');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => expect(mock.history.post).toHaveLength(1));
    expect(lastPost()).toEqual({
      url: '/auth/login/',
      body: { email: 'alice@example.com', password: 'Mango2026x' },
    });
  });

  it('attaches a server field error to the input it belongs to', async () => {
    mock.onPost('/auth/login/').reply(400, failed({
      message: 'Invalid input', errors: { email: ['Enter a valid email address.'] },
    }));
    renderForm(<LoginForm />);

    await fillIn('Email', 'alice@example.com');
    await fillIn('Password', 'Mango2026x');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByLabelText('Email')).toHaveAccessibleDescription('Enter a valid email address.');
    });
  });

  it('shows a rejected sign-in on the form, not only as a toast', async () => {
    mock.onPost('/auth/login/').reply(401, failed({
      message: 'Incorrect email or password', code: 'INVALID_CREDENTIALS',
    }));
    renderForm(<LoginForm />);

    await fillIn('Email', 'alice@example.com');
    await fillIn('Password', 'wrong-password');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password');
  });

  it('spells out why a locked account cannot sign in (D-024)', async () => {
    mock.onPost('/auth/login/').reply(403, failed({
      message: 'Your account has been locked',
      code: 'ACCOUNT_LOCKED',
      errors: { reason: ['Three no-shows in one month'] },
    }));
    renderForm(<LoginForm />);

    await fillIn('Email', 'alice@example.com');
    await fillIn('Password', 'Mango2026x');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Three no-shows in one month');
    expect(alert).toHaveTextContent(/administrator/i);
  });

  it('never reaches the admin portal from the public form (D-027)', async () => {
    mock.onPost('/auth/login/').reply(401, failed({
      message: 'Incorrect email or password', code: 'INVALID_CREDENTIALS',
    }));
    renderForm(<LoginForm />);

    
    await fillIn('Email', 'admin@marketlink.vn');
    await fillIn('Password', 'Mango2026x');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => expect(mock.history.post).toHaveLength(1));
    expect(mock.history.post.map((request) => request.url)).toEqual(['/auth/login/']);
  });
});

describe('RegisterCustomerForm (G-10)', () => {
  async function fillCustomer() {
    await fillIn('Full name', 'Alice Nguyen');
    await fillIn('Email', 'Alice@Example.com');
    await fillIn('Phone number', '0912345678');
    await fillIn('Address', '12 Market Street, District 1');
    await fillIn('Password', 'Mango2026x');
    await fillIn('Confirm password', 'Mango2026x');
  }

  it('sends exactly the body AU-01 declares', async () => {
    mock.onPost('/auth/register/customer/').reply(201, ok({ access: 'a', refresh: 'r', user: CUSTOMER }));
    renderForm(<RegisterCustomerForm />);

    await fillCustomer();
    await userEvent.click(screen.getByRole('button', { name: /create my account/i }));

    await waitFor(() => expect(mock.history.post).toHaveLength(1));
    const { url, body } = lastPost();
    expect(url).toBe('/auth/register/customer/');
    expect(Object.keys(body).sort()).toEqual([
      'address', 'confirm_password', 'email', 'full_name', 'password', 'phone',
    ]);
    expect(body.email).toBe('alice@example.com');
  });

  it('puts EMAIL_EXISTS under the email box', async () => {
    mock.onPost('/auth/register/customer/').reply(400, failed({
      message: 'Invalid input',
      code: 'EMAIL_EXISTS',
      errors: { email: ['This email is already registered.'] },
    }));
    renderForm(<RegisterCustomerForm />);

    await fillCustomer();
    await userEvent.click(screen.getByRole('button', { name: /create my account/i }));

    await waitFor(() => {
      expect(screen.getByLabelText('Email')).toHaveAccessibleDescription('This email is already registered.');
    });
  });
});

describe('RegisterFarmerForm (G-11)', () => {
  async function fillStep1() {
    await fillIn('Email', 'stall@example.com');
    await fillIn('Phone number', '0987654321');
    await fillIn('Password', 'Mango2026x');
    await fillIn('Confirm password', 'Mango2026x');
    await userEvent.click(screen.getByRole('button', { name: /continue/i }));
  }

  async function fillStep2() {
    await fillIn('Stall name', 'Green Stall');
    await fillIn('Contact person', 'Bob Tran');
    await fillIn('Address', '5 Farm Road, Da Lat');
  }

  it('will not submit without an operating day (D-031)', async () => {
    renderForm(<RegisterFarmerForm />);

    await fillStep1();
    await fillStep2();
    await userEvent.click(screen.getByRole('button', { name: /submit for review/i }));

    expect(await screen.findByText(/select at least one operating day/i)).toBeInTheDocument();
    expect(mock.history.post).toHaveLength(0);
  });

  it('sends the ticked days as ISO weekdays', async () => {
    mock.onPost('/auth/register/farmer/').reply(201, ok({ access: 'a', refresh: 'r', user: FARMER }));
    renderForm(<RegisterFarmerForm />);

    await fillStep1();
    await fillStep2();
    await userEvent.click(screen.getByRole('checkbox', { name: 'Monday' }));
    await userEvent.click(screen.getByRole('checkbox', { name: 'Wednesday' }));
    await userEvent.click(screen.getByRole('checkbox', { name: 'Sunday' }));
    await userEvent.click(screen.getByRole('button', { name: /submit for review/i }));

    await waitFor(() => expect(mock.history.post).toHaveLength(1));
    const { url, body } = lastPost();
    expect(url).toBe('/auth/register/farmer/');
    
    expect(body.operating_days).toEqual([1, 3, 7]);
    expect(Object.keys(body).sort()).toEqual([
      'address', 'confirm_password', 'contact_person', 'email', 'operating_days',
      'password', 'phone', 'stall_name',
    ]);
  });

  it('holds the new stall on an approval notice instead of a dashboard it has no access to', async () => {
    mock.onPost('/auth/register/farmer/').reply(201, ok({ access: 'a', refresh: 'r', user: FARMER }));
    renderForm(<RegisterFarmerForm />);

    await fillStep1();
    await fillStep2();
    await userEvent.click(screen.getByRole('checkbox', { name: 'Monday' }));
    await userEvent.click(screen.getByRole('button', { name: /submit for review/i }));

    expect(await screen.findByText(/awaiting administrator approval/i)).toBeInTheDocument();
    expect(navigate).not.toHaveBeenCalled();
    
    expect(useAuthStore.getState().accessToken).toBeNull();

    await userEvent.click(screen.getByRole('button', { name: /go to dashboard/i }));

    expect(useAuthStore.getState().accessToken).toBe('a');
    expect(navigate).toHaveBeenCalledWith('/farmer', { replace: true });
  });
});

describe('ChangePasswordForm (C-11 / F-11 / A-12)', () => {
  it('catches a mistyped confirmation before spending a request', async () => {
    renderForm(<ChangePasswordForm />);

    await fillIn('Current password', 'Mango2026x');
    await fillIn('New password', 'Papaya2027z');
    await fillIn('Confirm new password', 'Papaya2028q');
    await userEvent.click(screen.getByRole('button', { name: /change password/i }));

    await waitFor(() => {
      expect(screen.getByLabelText('Confirm new password'))
        .toHaveAccessibleDescription('Passwords do not match');
    });
    expect(mock.history.post).toHaveLength(0);
  });

  it('sends the three fields AU-07 requires', async () => {
    mock.onPost('/auth/change-password/').reply(200, ok({}));
    renderForm(<ChangePasswordForm />);

    await fillIn('Current password', 'Mango2026x');
    await fillIn('New password', 'Papaya2027z');
    await fillIn('Confirm new password', 'Papaya2027z');
    await userEvent.click(screen.getByRole('button', { name: /change password/i }));

    await waitFor(() => expect(mock.history.post).toHaveLength(1));
    const { url, body } = lastPost();
    expect(url).toBe('/auth/change-password/');
    expect(Object.keys(body).sort()).toEqual(['confirm_password', 'current_password', 'new_password']);
  });
});

describe('AdminLoginPage (A-00)', () => {
  it('offers no way to sign up or reset a password — IT issues the accounts (D-027)', () => {
    renderForm(<AdminLoginPage />);

    expect(screen.queryAllByRole('link')).toEqual([]);
  });

  it('signs in through the admin portal endpoint', async () => {
    mock.onPost('/auth/admin/login/').reply(200, ok({
      access: 'a', refresh: 'r', user: { ...CUSTOMER, role: 'ADMIN' },
    }));
    renderForm(<AdminLoginPage />);

    await fillIn('Email', 'admin@marketlink.vn');
    await fillIn('Password', 'Mango2026x');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => expect(mock.history.post).toHaveLength(1));
    expect(lastPost().url).toBe('/auth/admin/login/');
  });
});
