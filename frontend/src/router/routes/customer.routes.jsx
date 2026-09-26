import { ROLES } from '../../constants/roles';
import { CustomerLayout } from '../../layouts/CustomerLayout';
import { RequireAuth, RequireRole } from '../guards';

const page = (load) => async () => ({ Component: (await load()).default });

/** Nested under PublicLayout (see public.routes). */
export const customerRoutes = [
  {
    element: <RequireAuth />,
    children: [
      {
        element: <RequireRole allow={[ROLES.CUSTOMER]} />,
        children: [
          {
            element: <CustomerLayout />,
            children: [
              { path: '/customer', lazy: page(() => import('../../pages/customer/CustomerDashboard')) },
              { path: '/customer/cart', lazy: page(() => import('../../pages/customer/CartPage')) },
              { path: '/customer/checkout', lazy: page(() => import('../../pages/customer/CheckoutPage')) },
              { path: '/customer/checkout/success', lazy: page(() => import('../../pages/customer/CheckoutSuccessPage')) },
              { path: '/customer/orders', lazy: page(() => import('../../pages/customer/OrdersPage')) },
              { path: '/customer/orders/:id', lazy: page(() => import('../../pages/customer/OrderDetailPage')) },
              { path: '/customer/orders/:id/edit', lazy: page(() => import('../../pages/customer/EditOrderPage')) },
              { path: '/customer/orders/:id/review', lazy: page(() => import('../../pages/customer/ReviewOrderPage')) },
              { path: '/customer/favorites', lazy: page(() => import('../../pages/customer/FavoritesPage')) },
              { path: '/customer/profile', lazy: page(() => import('../../pages/customer/ProfilePage')) },
              { path: '/customer/notifications', lazy: page(() => import('../../pages/customer/NotificationsPage')) },
              { path: '/customer/password', lazy: page(() => import('../../pages/customer/ChangePasswordPage')) },
            ],
          },
        ],
      },
    ],
  },
];
