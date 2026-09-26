import PropTypes from 'prop-types';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { EmptyState } from '../components/feedback/EmptyState';
import { PageSkeleton } from '../components/feedback/PageSkeleton';
import { ROUTES, homePathForRole } from '../constants/routes';
import { useAuth } from '../hooks/authentication/useAuth';

// /auth/me/ failed for a reason other than an ended session (network, server error).
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

/** Sign-in and sign-up pages: signed-in users go to their own home. */
export function GuestOnly() {
  const { user, isAuthenticated, isLoading, isError, refetch } = useAuth();
  if (!isAuthenticated) return <Outlet />;
  if (isLoading) return <PageSkeleton />;
  if (isError) return <AccountLoadError onRetry={refetch} />;
  return <Navigate to={homePathForRole(user.role)} replace />;
}

/** Signed-in area: guests are sent to sign in and brought back afterwards. */
export function RequireAuth() {
  const location = useLocation();
  const { isAuthenticated, isLoading, isError, refetch } = useAuth();
  if (!isAuthenticated) return <Navigate to={ROUTES.LOGIN} replace state={{ from: location }} />;
  if (isLoading) return <PageSkeleton />;
  if (isError) return <AccountLoadError onRetry={refetch} />;
  return <Outlet />;
}

/** Place inside RequireAuth. */
export function RequireRole({ allow }) {
  const { user } = useAuth();
  if (!user) return <PageSkeleton />;
  if (!allow.includes(user.role)) return <Navigate to={ROUTES.FORBIDDEN} replace />;
  return <Outlet />;
}

RequireRole.propTypes = {
  allow: PropTypes.arrayOf(PropTypes.string).isRequired,
};
