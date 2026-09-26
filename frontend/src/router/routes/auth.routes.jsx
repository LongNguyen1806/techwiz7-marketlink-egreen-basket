import { AuthLayout } from '../../layouts/AuthLayout';
import { ROUTES } from '../../constants/routes';
import { GuestOnly } from '../guards';

// Route-level code splitting: the page module loads before the route renders.
const page = (load) => async () => ({ Component: (await load()).default });

export const authRoutes = [
  {
    element: <GuestOnly />,
    children: [
      {
        element: <AuthLayout />,
        children: [
          { path: ROUTES.LOGIN, lazy: page(() => import('../../pages/auth/LoginPage')) },
          { path: ROUTES.REGISTER_CUSTOMER, lazy: page(() => import('../../pages/guest/RegisterCustomerPage')) },
          { path: ROUTES.REGISTER_FARMER, lazy: page(() => import('../../pages/auth/RegisterFarmerPage')) },
        ],
      },
    ],
  },
];
