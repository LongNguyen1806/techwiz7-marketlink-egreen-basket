import { ROLES } from '../../constants/roles';
import { ROUTES } from '../../constants/routes';
import { FarmerLayout } from '../../layouts/FarmerLayout';
import { RequireAuth, RequireRole } from '../guards';

const page = (load) => async () => ({ Component: (await load()).default });


export const farmerRoutes = [
  {
    element: <RequireAuth />,
    children: [
      {
        element: <RequireRole allow={[ROLES.FARMER]} />,
        children: [
          {
            element: <FarmerLayout />,
            children: [
              { path: ROUTES.FARMER.HOME, lazy: page(() => import('../../pages/farmer/FarmerDashboardPage')) },
              { path: ROUTES.FARMER.STATS, lazy: page(() => import('../../pages/farmer/FarmerStatsPage')) },
              {
                path: ROUTES.FARMER.NOTIFICATIONS,
                lazy: page(() => import('../../pages/farmer/FarmerNotificationsPage')),
              },
              { path: ROUTES.FARMER.ORDERS, lazy: page(() => import('../../pages/farmer/FarmerOrdersPage')) },
              {
                path: `${ROUTES.FARMER.ORDERS}/:id`,
                lazy: page(() => import('../../pages/farmer/FarmerOrderDetailPage')),
              },
              { path: ROUTES.FARMER.PRODUCTS, lazy: page(() => import('../../pages/farmer/FarmerProductsPage')) },
              {
                path: ROUTES.FARMER.PRODUCT_NEW,
                lazy: page(() => import('../../pages/farmer/FarmerProductFormPage')),
              },
              {
                path: `${ROUTES.FARMER.PRODUCTS}/:id/edit`,
                lazy: page(() => import('../../pages/farmer/FarmerProductFormPage')),
              },
              {
                path: ROUTES.FARMER.STOCK_TEMPLATE,
                lazy: page(() => import('../../pages/farmer/FarmerStockTemplatePage')),
              },
              { path: ROUTES.FARMER.MARKETS, lazy: page(() => import('../../pages/farmer/FarmerMarketsPage')) },
              { path: ROUTES.FARMER.PROFILE, lazy: page(() => import('../../pages/farmer/FarmerProfilePage')) },
              { path: ROUTES.FARMER.REVIEWS, lazy: page(() => import('../../pages/farmer/FarmerReviewsPage')) },
              {
                path: ROUTES.FARMER.CHANGE_PASSWORD,
                lazy: page(() => import('../../pages/auth/ChangePasswordPage')),
              },
            ],
          },
        ],
      },
    ],
  },
];
