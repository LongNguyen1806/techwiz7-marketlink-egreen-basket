import { PublicLayout } from '../../layouts/PublicLayout';
import { customerRoutes } from './customer.routes';

const page = (load) => async () => ({ Component: (await load()).default });


export const publicRoutes = [
  {
    element: <PublicLayout />,
    children: [
      {
        path: '/',
        lazy: page(() => import('../../pages/guest/HomePage')),
      },
      {
        path: '/products',
        lazy: page(() => import('../../pages/guest/ProductsPage')),
      },
      {
        path: '/products/:id',
        lazy: page(() => import('../../pages/guest/ProductDetailPage')),
      },
      ...customerRoutes,
    ],
  },
];
