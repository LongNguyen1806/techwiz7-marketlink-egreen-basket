import { lazy } from 'react';
import { Suspend } from '../Suspend';
import { RequireRole } from '../guards';
import { AdminLayout } from '../../layouts/AdminLayout';

const AdminFarmersPage = lazy(() => import('../../pages/admin/AdminFarmersPage'));
const AdminFarmerDetailPage = lazy(() => import('../../pages/admin/AdminFarmerDetailPage'));
const AdminCustomerDetailPage = lazy(() => import('../../pages/admin/AdminCustomerDetailPage'));
const AdminMarketsPage = lazy(() => import('../../pages/admin/AdminMarketsPage'));
const AdminMarketFormPage = lazy(() => import('../../pages/admin/AdminMarketFormPage'));
const AdminCategoriesPage = lazy(() => import('../../pages/admin/AdminCategoriesPage'));
const AdminAnnouncementsPage = lazy(() => import('../../pages/admin/AdminAnnouncementsPage'));
const AdminAuditLogsPage = lazy(() => import('../../pages/admin/AdminAuditLogsPage'));
const ChangePasswordPage = lazy(() => import('../../pages/customer/ChangePasswordPage'));

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
                <AdminFarmersPage />
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
            path: '/admin/settings',
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
