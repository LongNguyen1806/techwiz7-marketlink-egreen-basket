import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ProfileEditDialog, VN_PHONE } from './ProfileEditDialog';
import { ApiError } from '../../lib/ApiError';
import { renderPage } from '../../test/render';

const FIELDS = [
  { required: true, name: 'full_name', label: 'Full name', value: 'Linh Pham', minLength: 2, maxLength: 100 },
  {
    required: true,
    name: 'phone',
    label: 'Phone',
    value: '0912345678',
    type: 'tel',
    pattern: VN_PHONE,
    patternMessage: 'Enter a Vietnamese mobile number, e.g. 0912345678.',
  },
  { required: true, name: 'address', label: 'Address', value: '12 Le Loi', minLength: 5, maxLength: 255 },
];

function open(onSave = vi.fn().mockResolvedValue({})) {
  renderPage(
    <ProfileEditDialog
      open
      onOpenChange={() => {}}
      title="Edit customer"
      note="Fix a typo."
      signInEmail="linh@example.com"
      fields={FIELDS}
      onSave={onSave}
    />,
  );
  return onSave;
}

describe('ProfileEditDialog: the same rules as registration', () => {
  it('shows the sign-in email but never lets it be edited', () => {
    open();
    expect(screen.getByLabelText('Email')).toBeDisabled();
  });

  it('refuses a one-letter name without calling the server', async () => {
    const onSave = open();
    const name = screen.getByLabelText(/Full name/);
    await userEvent.clear(name);
    await userEvent.type(name, 'L');
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(screen.getByText('Full name must be at least 2 characters.')).toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();
  });

  it('refuses a phone number that is not a Vietnamese mobile', async () => {
    const onSave = open();
    const phone = screen.getByLabelText(/Phone/);
    await userEvent.clear(phone);
    await userEvent.type(phone, '0123456789');
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(screen.getByText(/Vietnamese mobile number/)).toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();
  });

  it('refuses an emptied required field', async () => {
    const onSave = open();
    await userEvent.clear(screen.getByLabelText(/Address/));
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(screen.getByText('Address is required.')).toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();
  });

  it('sends only the fields that changed', async () => {
    const onSave = open();
    const address = screen.getByLabelText(/Address/);
    await userEvent.clear(address);
    await userEvent.type(address, '99 New Street');
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(onSave).toHaveBeenCalledWith({ address: '99 New Street' });
  });

  it('shows what the server refused under the right field', async () => {
    // What the axios client hands back: an ApiError carrying the field errors.
    const error = new ApiError({
      status: 400,
      code: 'VALIDATION_ERROR',
      fieldErrors: { phone: ['This phone number is already in use.'] },
    });
    const onSave = open(vi.fn().mockRejectedValue(error));
    const phone = screen.getByLabelText(/Phone/);
    await userEvent.clear(phone);
    await userEvent.type(phone, '0987654321');
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(onSave).toHaveBeenCalled();
    expect(await screen.findByText('This phone number is already in use.')).toBeInTheDocument();
  });
});
