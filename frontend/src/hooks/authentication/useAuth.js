import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocation, useNavigate } from 'react-router-dom';
import { authApi } from '../../api/common/authApi';
import { authKeys } from '../../constants/queryKeys';
import { ROLES } from '../../constants/roles';
import { ROUTES, homePathForRole } from '../../constants/routes';
import { STALE } from '../../constants/staleTimes';
import { notify } from '../../lib/toast';
import { selectIsAuthenticated, useAuthStore } from '../../stores/auth.store';


const ROLE_AREAS = {
  '/farmer': ROLES.FARMER,
  '/customer': ROLES.CUSTOMER,
  '/admin': ROLES.ADMIN,
};

function redirectAfterSignIn(location, role) {
  const from = location.state?.from?.pathname;
  if (from) {
    const area = Object.keys(ROLE_AREAS).find((prefix) => from.startsWith(prefix));
    if (!area || ROLE_AREAS[area] === role) return from;
  }
  return homePathForRole(role);
}

export function useIsAuthenticated() {
  return useAuthStore(selectIsAuthenticated);
}

export function useCurrentUser() {
  const isAuthenticated = useIsAuthenticated();
  return useQuery({
    queryKey: authKeys.me(),
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
  useEffect(
    () =>
      useAuthStore.subscribe((state, previous) => {
        if (previous.userId !== null && state.userId !== previous.userId) {
          queryClient.clear();
        }
      }),
    [queryClient],
  );
}


function useStartSession() {
  const queryClient = useQueryClient();
  const setTokens = useAuthStore((state) => state.setTokens);
  const navigate = useNavigate();
  const location = useLocation();

  return ({ access, refresh, user }) => {
    setTokens({ access, refresh });
    queryClient.setQueryData(authKeys.me(), user);
    navigate(redirectAfterSignIn(location, user.role), { replace: true });
  };
}

export function useLogin() {
  const startSession = useStartSession();
  return useMutation({
    mutationFn: authApi.login,
    onSuccess: (session) => {
      startSession(session);
      notify.success(`Welcome back, ${session.user.display_name}`);
    },
  });
}

export function useRegisterFarmer() {
  const startSession = useStartSession();
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

export function useRegisterCustomer() {
  const startSession = useStartSession();
  return useMutation({
    mutationFn: authApi.registerCustomer,
    onSuccess: (session) => {
      startSession(session);
      notify.success('Welcome to MarketLink', { description: 'Your account is ready.' });
    },
  });
}

export function useLogout() {
  const navigate = useNavigate();
  return useMutation({
    mutationFn: () => {
      const { refreshToken } = useAuthStore.getState();
      return refreshToken ? authApi.logout(refreshToken) : Promise.resolve();
    },
    
    meta: { silent: true },
    onSettled: () => {
      useAuthStore.getState().clearSession();
      navigate(ROUTES.LOGIN, { replace: true });
      notify.success('You have signed out');
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: authApi.changePassword,
    meta: {
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
