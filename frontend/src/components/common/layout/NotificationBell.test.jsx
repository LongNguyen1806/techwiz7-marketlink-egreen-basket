import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { NotificationBell } from './NotificationBell';
import { renderPage } from '../../../test/render';

vi.mock('../../../hooks/queries/common/useNotifications', () => ({
  useNotifications: () => ({
    unread: 1,
    latest: [
      {
        id: 5,
        title: 'AI approved 3 listing(s)',
        message: 'Latest: Spinach (Green Farm). Check them in AI decisions.',
        target_url: '/admin/ai-decisions',
        is_read: false,
        created_at: new Date().toISOString(),
      },
    ],
    markAll: { mutate: vi.fn() },
    markOne: { mutate: vi.fn() },
  }),
}));

describe('notification bell (#7)', () => {
  it('shows the unread count and the grouped AI notice with its link', async () => {
    renderPage(<NotificationBell role="ADMIN" />);

    expect(screen.getByText('1')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Notifications' }));

    expect(await screen.findByText('AI approved 3 listing(s)')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'View details' })).toHaveAttribute('href', '/admin/ai-decisions');
  });

  it('has no "View all" link where there is no full list (the admin portal)', async () => {
    renderPage(<NotificationBell role="ADMIN" />);
    await userEvent.click(screen.getByRole('button', { name: 'Notifications' }));

    await screen.findByText('AI approved 3 listing(s)');
    expect(screen.queryByText('View all')).not.toBeInTheDocument();
  });

  it('keeps "View all" for the portals that have a list', async () => {
    renderPage(<NotificationBell role="FARMER" listPath="/farmer/notifications" />);
    await userEvent.click(screen.getByRole('button', { name: 'Notifications' }));

    expect(await screen.findByRole('menuitem', { name: 'View all' })).toBeInTheDocument();
  });
});
