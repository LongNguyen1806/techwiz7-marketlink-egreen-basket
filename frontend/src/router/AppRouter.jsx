import { Navigate, Outlet, ScrollRestoration, createBrowserRouter, useRouteError } from 'react-router-dom';
import { EmptyState } from '../components/feedback/EmptyState';
import { PageSkeleton } from '../components/feedback/PageSkeleton';
import { ROUTES, homePathForRole } from '../constants/routes';
import { useAuth } from '../hooks/authentication/useAuth';
import NotFoundPage from '../pages/errors/NotFoundPage';
import { authRoutes } from './routes/auth.routes';
import { farmerRoutes } from './routes/farmer.routes';

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

// "/" is the public home, which arrives with the guest branch. Until then guests go to
// sign in and signed-in users to their own area.
function HomeRoute() {
  const { user, isAuthenticated, isLoading } = useAuth();
  if (!isAuthenticated) return <Navigate to={ROUTES.LOGIN} replace />;
  if (isLoading || !user) return <PageSkeleton />;
  const home = homePathForRole(user.role);
  return home === ROUTES.HOME ? <NotFoundPage /> : <Navigate to={home} replace />;
}

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    errorElement: <RouteErrorPage />,
    hydrateFallbackElement: <PageSkeleton />,
    children: [
      { index: true, element: <HomeRoute /> },
      ...authRoutes,
      ...farmerRoutes,
      { path: ROUTES.FORBIDDEN, lazy: page(() => import('../pages/errors/ForbiddenPage')) },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
