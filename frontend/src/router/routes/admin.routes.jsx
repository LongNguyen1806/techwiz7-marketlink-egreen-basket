import { lazy } from 'react';

import { Suspend } from '../Suspend';
import { RequireRole } from '../guards';
import { AdminLayout } from '../../layouts/AdminLayout';

const AdminDashboardPage = lazy(() => import('@/pages/admin/AdminDashboardPage'));
const AdminFarmersPage = lazy(() => import('@/pages/admin/AdminFarmersPage'));
const AdminFarmerDetailPage = lazy(() => import('@/pages/admin/AdminFarmerDetailPage'));
const AdminCustomersPage = lazy(() => import('@/pages/admin/AdminCustomersPage'));
const AdminOrdersPage = lazy(() => import('@/pages/admin/AdminOrdersPage'));
const AdminQueuePage = lazy(() => import('@/pages/admin/AdminQueuePage'));
const AdminSettingsPage = lazy(() => import('@/pages/admin/AdminSettingsPage'));
const AdminCustomerDetailPage = lazy(
  () => import('@/pages/admin/AdminCustomerDetailPage'),
);
const AdminMarketsPage = lazy(() => import('@/pages/admin/AdminMarketsPage'));
const AdminMarketFormPage = lazy(() => import('@/pages/admin/AdminMarketFormPage'));
const AdminCategoriesPage = lazy(() => import('@/pages/admin/AdminCategoriesPage'));
const AdminModerationPage = lazy(() => import('@/pages/admin/AdminModerationPage'));
const AdminReportsPage = lazy(() => import('@/pages/admin/AdminReportsPage'));
const AdminAnnouncementsPage = lazy(() => import('@/pages/admin/AdminAnnouncementsPage'));
const AdminAuditLogsPage = lazy(() => import('@/pages/admin/AdminAuditLogsPage'));
const ChangePasswordPage = lazy(() => import('@/pages/auth/ChangePasswordPage'));

/** Nested under a shared RequireAuth parent in AppRouter. */
export const adminRoutes = [
  {
    element: <RequireRole allow={['ADMIN']} />,
    children: [
      {
        element: <AdminLayout />,
        children: [
          {
            path: '/admin',
            element: (
              <Suspend>
                <AdminDashboardPage />
              </Suspend>
            ),
          },
          {
            path: '/admin/farmers',
            element: (
              <Suspend>
                <AdminFarmersPage />
              </Suspend>
            ),
          },
          {
            path: '/admin/farmers/:id',
            element: (
              <Suspend>
                <AdminFarmerDetailPage />
              </Suspend>
            ),
          },
          {
            path: '/admin/customers/:id',
            element: (
              <Suspend>
                <AdminCustomerDetailPage />
              </Suspend>
            ),
          },
          {
            path: '/admin/customers',
            element: (
              <Suspend>
                <AdminCustomersPage />
              </Suspend>
            ),
          },
          {
            path: '/admin/orders',
            element: (
              <Suspend>
                <AdminOrdersPage />
              </Suspend>
            ),
          },
          {
            path: '/admin/queue',
            element: (
              <Suspend>
                <AdminQueuePage />
              </Suspend>
            ),
          },
          {
            path: '/admin/limits',
            element: (
              <Suspend>
                <AdminSettingsPage />
              </Suspend>
            ),
          },
          {
            path: '/admin/markets',
            element: (
              <Suspend>
                <AdminMarketsPage />
              </Suspend>
            ),
          },
          {
            path: '/admin/markets/new',
            element: (
              <Suspend>
                <AdminMarketFormPage />
              </Suspend>
            ),
          },
          {
            path: '/admin/markets/:id/edit',
            element: (
              <Suspend>
                <AdminMarketFormPage />
              </Suspend>
            ),
          },
          {
            path: '/admin/categories',
            element: (
              <Suspend>
                <AdminCategoriesPage />
              </Suspend>
            ),
          },
          {
            path: '/admin/moderation',
            element: (
              <Suspend>
                <AdminModerationPage />
              </Suspend>
            ),
          },
          {
            path: '/admin/reports',
            element: (
              <Suspend>
                <AdminReportsPage />
              </Suspend>
            ),
          },
          {
            path: '/admin/announcements',
            element: (
              <Suspend>
                <AdminAnnouncementsPage />
              </Suspend>
            ),
          },
          {
            path: '/admin/audit-logs',
            element: (
              <Suspend>
                <AdminAuditLogsPage />
              </Suspend>
            ),
          },
          {
            path: '/admin/password',
            element: (
              <Suspend>
                <ChangePasswordPage />
              </Suspend>
            ),
          },
        ],
      },
    ],
  },
];
