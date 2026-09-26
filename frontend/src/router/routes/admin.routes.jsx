import { ROLES } from '../../constants/roles';
import { AdminLayout } from '../../layouts/AdminLayout';
import { RequireAuth, RequireRole } from '../guards';

const page = (load) => async () => ({ Component: (await load()).default });

export const adminRoutes = [
  {
    element: <RequireAuth />,
    children: [
      {
        element: <RequireRole allow={[ROLES.ADMIN]} />,
        children: [
          {
            element: <AdminLayout />,
            children: [
              { path: '/admin', lazy: page(() => import('../../pages/admin/AdminFarmersPage')) },
              { path: '/admin/farmers', lazy: page(() => import('../../pages/admin/AdminFarmersPage')) },
              { path: '/admin/farmers/:id', lazy: page(() => import('../../pages/admin/AdminFarmerDetailPage')) },
              { path: '/admin/customers/:id', lazy: page(() => import('../../pages/admin/AdminCustomerDetailPage')) },
              { path: '/admin/markets', lazy: page(() => import('../../pages/admin/AdminMarketsPage')) },
              { path: '/admin/markets/new', lazy: page(() => import('../../pages/admin/AdminMarketFormPage')) },
              { path: '/admin/markets/:id/edit', lazy: page(() => import('../../pages/admin/AdminMarketFormPage')) },
              { path: '/admin/categories', lazy: page(() => import('../../pages/admin/AdminCategoriesPage')) },
              { path: '/admin/announcements', lazy: page(() => import('../../pages/admin/AdminAnnouncementsPage')) },
              { path: '/admin/audit-logs', lazy: page(() => import('../../pages/admin/AdminAuditLogsPage')) },
              { path: '/admin/settings', lazy: page(() => import('../../pages/customer/ChangePasswordPage')) },
            ],
          },
        ],
      },
    ],
  },
];
