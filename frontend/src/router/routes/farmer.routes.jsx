import { ROLES } from '../../constants/roles';
import { ROUTES } from '../../constants/routes';
import { RequireAuth, RequireRole } from '../guards';

const page = (load) => async () => ({ Component: (await load()).default });

// FarmerLayout and the farmer pages join here slice by slice as their logic is rewritten.
export const farmerRoutes = [
  {
    element: <RequireAuth />,
    children: [
      {
        element: <RequireRole allow={[ROLES.FARMER]} />,
        children: [
          { path: ROUTES.FARMER.CHANGE_PASSWORD, lazy: page(() => import('../../pages/auth/ChangePasswordPage')) },
        ],
      },
    ],
  },
];
