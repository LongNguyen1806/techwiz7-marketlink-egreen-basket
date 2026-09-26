import { lazy } from 'react';
import { Suspend } from '../Suspend';
import { GuestOnly } from '../guards';
import { AdminAuthLayout } from '../../layouts/AdminAuthLayout';

const AdminLoginPage = lazy(() => import('../../pages/admin/AdminLoginPage'));

/**
 * A-00. Its own portal (D-027): AU-09 accepts admins only, and AU-03 rejects them, so the two
 * sign-in pages never share a form.
 */
export const adminAuthRoutes = [
  {
    element: <GuestOnly />,
    children: [
      {
        element: <AdminAuthLayout />,
        children: [
          {
            path: '/admin/login',
            element: (
              <Suspend>
                <AdminLoginPage />
              </Suspend>
            ),
          },
        ],
      },
    ],
  },
];
