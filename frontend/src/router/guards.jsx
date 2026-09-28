import PropTypes from 'prop-types';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { EmptyState } from '../components/feedback/EmptyState';
import { PageSkeleton } from '../components/feedback/PageSkeleton';
import { ROLES } from '../constants/roles';
import { ROUTES, homePathForRole } from '../constants/routes';
import { loginPathFor, useAuth, usePortal } from '../hooks/authentication/useAuth';


function AccountLoadError({ onRetry }) {
  return (
    <EmptyState
      title="We couldn't load your account"
      description="Check your connection and try again."
      actionLabel="Try again"
      onAction={() => onRetry()}
    />
  );
}

AccountLoadError.propTypes = {
  onRetry: PropTypes.func.isRequired,
};


export function GuestOnly() {
  const { user, isAuthenticated, isLoading, isError, refetch } = useAuth();
  if (!isAuthenticated) return <Outlet />;
  if (isLoading) return <PageSkeleton />;
  if (isError) return <AccountLoadError onRetry={refetch} />;
  return <Navigate to={homePathForRole(user.role)} replace />;
}


export function NotForFarmers() {
  const { user, isAuthenticated, isLoading } = useAuth();
  if (!isAuthenticated) return <Outlet />;
  if (isLoading) return <PageSkeleton />;
  if (user?.role === ROLES.FARMER) return <Navigate to={ROUTES.FARMER.HOME} replace />;
  return <Outlet />;
}


export function RequireAuth() {
  const location = useLocation();
  const portal = usePortal();
  const { isAuthenticated, isLoading, isError, refetch } = useAuth();
  if (!isAuthenticated) return <Navigate to={loginPathFor(portal)} replace state={{ from: location }} />;
  if (isLoading) return <PageSkeleton />;
  if (isError) return <AccountLoadError onRetry={refetch} />;
  return <Outlet />;
}


export function RequireRole({ allow }) {
  const { user } = useAuth();
  if (!user) return <PageSkeleton />;
  if (!allow.includes(user.role)) return <Navigate to={ROUTES.FORBIDDEN} replace />;
  return <Outlet />;
}

RequireRole.propTypes = {
  allow: PropTypes.arrayOf(PropTypes.string).isRequired,
};
