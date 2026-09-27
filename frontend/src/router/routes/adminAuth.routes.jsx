import { AdminAuthLayout } from '../../layouts/AdminAuthLayout';
import { GuestOnly } from '../guards';

const page = (load) => async () => ({ Component: (await load()).default });


export const adminAuthRoutes = [
  {
    element: <GuestOnly />,
    children: [
      {
        element: <AdminAuthLayout />,
        children: [
          {
            path: '/admin/login',
            lazy: page(() => import('../../pages/admin/AdminLoginPage')),
          },
        ],
      },
    ],
  },
];
