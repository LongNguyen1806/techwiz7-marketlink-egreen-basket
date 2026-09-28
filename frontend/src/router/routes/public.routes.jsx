import { PublicLayout } from '../../layouts/PublicLayout';
import { NotForFarmers } from '../guards';
import { customerRoutes } from './customer.routes';

const page = (load) => async () => ({ Component: (await load()).default });


export const publicRoutes = [
  {
    element: <NotForFarmers />,
    children: [
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
      {
        path: '/markets',
        lazy: page(() => import('../../pages/guest/MarketsPage')),
      },
      {
        path: '/markets/:id',
        lazy: page(() => import('../../pages/guest/MarketDetailPage')),
      },
      {
        path: '/farmers',
        lazy: page(() => import('../../pages/guest/FarmersPage')),
      },
      {
        path: '/farmers/:id',
        lazy: page(() => import('../../pages/guest/FarmerDetailPage')),
      },
      {
        path: '/about',
        lazy: page(() => import('../../pages/guest/AboutPage')),
      },
      {
        path: '/contact',
        lazy: page(() => import('../../pages/guest/ContactPage')),
      },
      {
        path: '/privacy',
        lazy: page(() => import('../../pages/guest/PrivacyPolicyPage')),
      },
      {
        path: '/sitemap',
        lazy: page(() => import('../../pages/guest/SitemapPage')),
      },
      ...customerRoutes,
    ],
  },
    ],
  },
];
