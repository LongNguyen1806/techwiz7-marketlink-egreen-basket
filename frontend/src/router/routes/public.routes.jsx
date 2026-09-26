import { lazy } from 'react';
import { Suspend } from '../Suspend';
import { PublicLayout } from '../../layouts/PublicLayout';
import { customerRoutes } from './customer.routes';

const HomePage = lazy(() => import('../../pages/guest/HomePage'));

/**
 * The storefront shell. Signed-in customer screens nest inside it too, so the header, the cart
 * drawer and the notification bell stay in place while browsing (C-00 → C-11).
 *
 * G-02 → G-08 and G-13 (markets, products, farmers, about, contact) belong to the Guest scope,
 * which the Admin branch owns. Add them here as they land: one entry each, same shape as '/'.
 */
export const publicRoutes = [
  {
    element: <PublicLayout />,
    children: [
      {
        path: '/',
        element: (
          <Suspend>
            <HomePage />
          </Suspend>
        ),
      },
      ...customerRoutes,
    ],
  },
];
