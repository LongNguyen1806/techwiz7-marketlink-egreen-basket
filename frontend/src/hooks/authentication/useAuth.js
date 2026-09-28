import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocation, useNavigate } from 'react-router-dom';
import { authApi } from '../../api/common/authApi';
import { authKeys } from '../../constants/queryKeys';
import { ROLES } from '../../constants/roles';
import { ROUTES, homePathForRole } from '../../constants/routes';
import { STALE } from '../../constants/staleTimes';
import { notify } from '../../lib/toast';
import {
  PORTALS,
  authStoreFor,
  currentPortal,
  portalForPath,
  selectIsAuthenticated,
  useAdminAuthStore,
  useMarketAuthStore,
} from '../../stores/auth.store';

const ROLE_AREAS = {
  '/farmer': ROLES.FARMER,
  '/customer': ROLES.CUSTOMER,
  '/admin': ROLES.ADMIN,
};

const LOGIN_PATH = {
  [PORTALS.MARKET]: ROUTES.LOGIN,
  [PORTALS.ADMIN]: ROUTES.ADMIN.LOGIN,
};

export function loginPathFor(portal) {
  return LOGIN_PATH[portal] ?? ROUTES.LOGIN;
}

function redirectAfterSignIn(location, role) {
  const from = location.state?.from?.pathname;
  if (from) {
    const area = Object.keys(ROLE_AREAS).find((prefix) => from.startsWith(prefix));
    if (!area || ROLE_AREAS[area] === role) return from;
  }
  return homePathForRole(role);
}

export function usePortal() {
  const { pathname } = useLocation();
  return portalForPath(pathname);
}

export function useIsAuthenticated() {
  const portal = usePortal();
  const market = useMarketAuthStore(selectIsAuthenticated);
  const admin = useAdminAuthStore(selectIsAuthenticated);
  return portal === PORTALS.ADMIN ? admin : market;
}

export function useCurrentUser() {
  const portal = usePortal();
  const isAuthenticated = useIsAuthenticated();
  return useQuery({
    queryKey: authKeys.me(portal),
    queryFn: ({ signal }) => authApi.me({ signal }),
    enabled: isAuthenticated,
    staleTime: STALE.SESSION,
  });
}

export function useAuth() {
  const isAuthenticated = useIsAuthenticated();
  const meQuery = useCurrentUser();
  const user = isAuthenticated ? (meQuery.data ?? null) : null;
  return {
    user,
    role: user?.role ?? null,
    isAuthenticated,
    isLoading: isAuthenticated && meQuery.isPending,
    isError: isAuthenticated && meQuery.isError && !user,
    refetch: meQuery.refetch,
  };
}

export function useAuthSessionSync() {
  const queryClient = useQueryClient();
  useEffect(() => {
    const watch = (portal) =>
      authStoreFor(portal).subscribe((state, previous) => {
        if (previous.userId === null || state.userId === previous.userId) return;
        if (currentPortal() === portal) queryClient.clear();
        else queryClient.removeQueries({ queryKey: authKeys.me(portal) });
      });
    const unsubscribes = [watch(PORTALS.MARKET), watch(PORTALS.ADMIN)];
    return () => unsubscribes.forEach((unsubscribe) => unsubscribe());
  }, [queryClient]);
}

function useStartSession(portal) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();

  return ({ access, refresh, user }) => {
    authStoreFor(portal).getState().setTokens({ access, refresh });
    queryClient.setQueryData(authKeys.me(portal), user);
    navigate(redirectAfterSignIn(location, user.role), { replace: true });
  };
}

export function useLogin() {
  const startSession = useStartSession(PORTALS.MARKET);
  return useMutation({
    mutationFn: authApi.login,
    onSuccess: (session) => {
      startSession(session);
      notify.success(`Welcome back, ${session.user.display_name}`);
    },
  });
}

export function useAdminLogin() {
  const startSession = useStartSession(PORTALS.ADMIN);
  return useMutation({
    mutationFn: authApi.adminLogin,
    meta: { silent: true },
    onSuccess: (session) => {
      startSession(session);
      notify.success(`Welcome back, ${session.user.display_name}`);
    },
  });
}

export function useRegisterFarmer() {
  const startSession = useStartSession(PORTALS.MARKET);
  return useMutation({
    mutationFn: authApi.registerFarmer,
    onSuccess: (session) => {
      startSession(session);
      notify.success('Your stall application has been sent', {
        description: "We'll let you know as soon as an administrator approves it.",
      });
    },
  });
}

export function useRegisterCustomer({ silent = false } = {}) {
  const startSession = useStartSession(PORTALS.MARKET);
  return useMutation({
    mutationFn: authApi.registerCustomer,
    meta: { silent },
    onSuccess: (session) => {
      startSession(session);
      notify.success('Welcome to MarketLink', { description: 'Your account is ready.' });
    },
  });
}

export function useLogout() {
  const navigate = useNavigate();
  const portal = usePortal();
  return useMutation({
    mutationFn: () => {
      const { refreshToken } = authStoreFor(portal).getState();
      return refreshToken ? authApi.logout(refreshToken) : Promise.resolve();
    },
    meta: { silent: true },
    onSettled: () => {
      authStoreFor(portal).getState().clearSession();
      navigate(loginPathFor(portal), { replace: true });
      notify.success('You have signed out');
    },
  });
}

export function useChangePassword({ silent = false } = {}) {
  return useMutation({
    mutationFn: authApi.changePassword,
    meta: {
      silent,
      errorMessages: {
        THROTTLED: {
          title: 'Too many attempts',
          description: 'Please wait a minute before trying to change your password again.',
        },
      },
    },
    onSuccess: () => {
      notify.success('Password changed', { description: 'Other devices have been signed out.' });
    },
  });
}
