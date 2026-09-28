import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AdminAIDecisionsPage from './AdminAIDecisionsPage';
import { adminApi } from '../../api/admin/adminApi';
import { renderPage } from '../../test/render';

vi.mock('../../api/admin/adminApi', () => ({
  adminApi: {
    getAIDecisions: vi.fn(),
    checkAIDecision: vi.fn(),
    approveProduct: vi.fn(),
    rejectProduct: vi.fn(),
  },
}));

const product = (id, name) => ({
  id,
  name,
  stall_name: 'Green Farm',
  farmer_id: 7,
  category: 'Greens',
  review_status: 'APPROVED',
  image: null,
});

const APPROVED = {
  id: 1,
  product: product(11, 'Cucumber'),
  verdict: 'PASS',
  risk_score: 0,
  summary: 'No problems found.',
  findings: [],
  auto_action: 'APPROVED',
  auto_action_at: '2026-09-28T09:00:00+07:00',
  admin_decision: null,
  admin_checked_at: null,
  checked_by: null,
};
const HELD = {
  ...APPROVED,
  id: 2,
  product: { ...product(12, 'iPhone 12'), review_status: 'PENDING' },
  verdict: 'LIKELY_VIOLATION',
  risk_score: 90,
  summary: 'A phone, not food.',
  findings: [{ severity: 'HIGH', message: 'A phone, not food.' }],
  auto_action: 'HELD',
};

function page(results) {
  return { results, count: results.length, page: 1, page_size: 20, total_pages: 1 };
}

function rowFor(name) {
  return screen.getByText(name).closest('li');
}

describe('AI decisions page (#8)', () => {
  beforeEach(() => {
    adminApi.getAIDecisions.mockResolvedValue(page([APPROVED, HELD]));
    adminApi.checkAIDecision.mockResolvedValue({ ...APPROVED, admin_checked_at: 'now' });
    adminApi.approveProduct.mockResolvedValue({});
    adminApi.rejectProduct.mockResolvedValue({});
  });

  it('lists what the AI approved and held, unchecked first', async () => {
    renderPage(<AdminAIDecisionsPage />);

    expect(await screen.findByText('Cucumber')).toBeInTheDocument();
    expect(within(rowFor('Cucumber')).getByText('Approved by AI')).toBeInTheDocument();
    expect(within(rowFor('iPhone 12')).getByText('Held by AI')).toBeInTheDocument();
    expect(adminApi.getAIDecisions).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, page_size: 20 }),
      expect.anything(),
    );
  });

  it('marks a decision as checked', async () => {
    renderPage(<AdminAIDecisionsPage />);
    await screen.findByText('Cucumber');

    await userEvent.click(within(rowFor('Cucumber')).getByRole('button', { name: 'Looks right' }));

    await waitFor(() => expect(adminApi.checkAIDecision).toHaveBeenCalledWith(1));
  });

  it('asks why before taking an AI approval off sale', async () => {
    renderPage(<AdminAIDecisionsPage />);
    await screen.findByText('Cucumber');

    await userEvent.click(within(rowFor('Cucumber')).getByRole('button', { name: 'Take off sale' }));
    const dialog = await screen.findByRole('dialog');
    const confirm = within(dialog).getByRole('button', { name: 'Take off sale' });
    expect(confirm).toBeDisabled();

    await userEvent.type(within(dialog).getByRole('textbox'), 'Wrong photo');
    expect(confirm).toBeEnabled();
    await userEvent.click(confirm);

    await waitFor(() => expect(adminApi.rejectProduct).toHaveBeenCalledWith(11, 'Wrong photo'));
  });

  it('approves a held listing when the admin disagrees with the AI', async () => {
    renderPage(<AdminAIDecisionsPage />);
    await screen.findByText('iPhone 12');

    await userEvent.click(within(rowFor('iPhone 12')).getByRole('button', { name: 'Approve anyway' }));

    await waitFor(() => expect(adminApi.approveProduct).toHaveBeenCalledWith(12));
  });

  it('says so when there is nothing left to check', async () => {
    adminApi.getAIDecisions.mockResolvedValue(page([]));
    renderPage(<AdminAIDecisionsPage />);

    expect(await screen.findByText('Nothing to check')).toBeInTheDocument();
  });
});
