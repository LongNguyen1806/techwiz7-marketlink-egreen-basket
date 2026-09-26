import { Outlet, ScrollRestoration, createBrowserRouter, useRouteError } from 'react-router-dom';
import { EmptyState } from '../components/feedback/EmptyState';
import { PageSkeleton } from '../components/feedback/PageSkeleton';
import { ROUTES } from '../constants/routes';
import NotFoundPage from '../pages/errors/NotFoundPage';
import { publicRoutes } from './routes/public.routes';
import { authRoutes } from './routes/auth.routes';
import { adminAuthRoutes } from './routes/adminAuth.routes';
import { farmerRoutes } from './routes/farmer.routes';
import { adminRoutes } from './routes/admin.routes';

const page = (load) => async () => ({ Component: (await load()).default });

function AppShell() {
  return (
    <>
      <Outlet />
      <ScrollRestoration />
    </>
  );
}

// Render errors and failed page downloads (e.g. an old tab after a new deploy) land here.
function RouteErrorPage() {
  const error = useRouteError();
  if (import.meta.env.DEV) console.error(error);
  return (
    <EmptyState
      title="Something went wrong"
      description="This page ran into a problem. Reloading usually fixes it."
      actionLabel="Reload page"
      onAction={() => window.location.reload()}
    />
  );
}

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    errorElement: <RouteErrorPage />,
    hydrateFallbackElement: <PageSkeleton />,
    children: [
      ...publicRoutes,
      ...authRoutes,
      ...adminAuthRoutes,
      ...farmerRoutes,
      ...adminRoutes,
      { path: ROUTES.FORBIDDEN, lazy: page(() => import('../pages/errors/ForbiddenPage')) },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
