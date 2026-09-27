import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocation, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import { authApi } from '../../api/common/authApi';
import { ApiError } from '@/lib/ApiError';
import { DASHBOARD_PATH, QUERY_KEYS, STALE } from '@/config/constants';
import {
  PORTALS,
  authStoreFor,
  portalForPath,
  selectIsAuthenticated,
  useAdminAuthStore,
  useMarketAuthStore,
} from '@/stores/auth.store';

function homePathForRole(role) {
  if (role === 'ADMIN') return DASHBOARD_PATH.ADMIN;
  if (role === 'FARMER') return DASHBOARD_PATH.FARMER;
  return DASHBOARD_PATH.CUSTOMER;
}

const LOGIN_PATH = {
  [PORTALS.MARKET]: '/login',
  [PORTALS.ADMIN]: '/admin/login',
};

export function loginPathFor(portal) {
  return LOGIN_PATH[portal] ?? LOGIN_PATH[PORTALS.MARKET];
}

/** Which session this page belongs to: `/admin/*` is the admin portal, the rest is the market. */
export function usePortal() {
  const { pathname } = useLocation();
  return portalForPath(pathname);
}

function reportUnlessFieldErrors(error) {
  const apiError = ApiError.fromUnknown(error);
  if (Object.keys(apiError.fieldErrors).length === 0) {
    toast.error(apiError.friendlyMessage);
  }
}

export function useAuth() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const portal = usePortal();

  // Both stores are subscribed to unconditionally so the hook order never changes when a
  // navigation moves this component from one portal to the other. A boolean is selected
  // rather than the state object, which zustand replaces on every write.
  const marketAuthed = useMarketAuthStore(selectIsAuthenticated);
  const adminAuthed = useAdminAuthStore(selectIsAuthenticated);
  const isAuthenticated = portal === PORTALS.ADMIN ? adminAuthed : marketAuthed;

  const meQuery = useQuery({
    queryKey: QUERY_KEYS.ME(portal),
    queryFn: authApi.me,
    enabled: isAuthenticated,
    staleTime: STALE.SESSION,
    retry: false,
  });

  // Sign-in writes to the portal the user is signing in to, which is where the form lives.
  const startSession = (targetPortal) => (data) => {
    authStoreFor(targetPortal).getState().setTokens({
      access: data.access,
      refresh: data.refresh,
      role: data.user.role,
    });
    queryClient.setQueryData(QUERY_KEYS.ME(targetPortal), data.user);
    navigate(homePathForRole(data.user.role), { replace: true });
  };

  // Clearing the cache is safe here because a react-query cache belongs to one tab, and this
  // tab is being sent to a login screen. What must survive is the *other portal's tokens*,
  // and those live in their own store, which this does not touch.
  const endSession = () => {
    authStoreFor(portal).getState().clearSession();
    queryClient.clear();
    navigate(loginPathFor(portal), { replace: true });
  };

  const loginMutation = useMutation({
    mutationFn: authApi.login,
    onSuccess: (data) => {
      startSession(PORTALS.MARKET)(data);
      toast.success('Welcome back — you are signed in');
    },
    onError: reportUnlessFieldErrors,
  });

  const adminLoginMutation = useMutation({
    mutationFn: authApi.adminLogin,
    onSuccess: (data) => {
      startSession(PORTALS.ADMIN)(data);
      toast.success('Welcome back — you are signed in');
    },
    onError: reportUnlessFieldErrors,
  });

  const logoutMutation = useMutation({
    mutationFn: async () => {
      const { accessToken } = authStoreFor(portal).getState();
      try {
        if (accessToken) await authApi.logout(accessToken);
      } catch {
        // Clear the local session even if the API call fails.
      }
    },
    onSettled: endSession,
  });

  const changePasswordMutation = useMutation({
    mutationFn: authApi.changePassword,
    onSuccess: () => {
      toast.success('Password updated — please sign in again.');
      endSession();
    },
    onError: reportUnlessFieldErrors,
  });

  const registerCustomerMutation = useMutation({
    mutationFn: authApi.registerCustomer,
    onSuccess: (data) => {
      startSession(PORTALS.MARKET)(data);
      toast.success('Account created — welcome to MarketLink');
    },
    onError: reportUnlessFieldErrors,
  });

  const registerFarmerMutation = useMutation({
    mutationFn: authApi.registerFarmer,
    onSuccess: (data) => {
      startSession(PORTALS.MARKET)(data);
      toast.success('Stall submitted — we will review it shortly.');
    },
    onError: reportUnlessFieldErrors,
  });

  return {
    portal,
    user: meQuery.data,
    isLoadingMe: meQuery.isLoading,
    isAuthenticated,
    login: loginMutation.mutateAsync,
    loginPending: loginMutation.isPending,
    adminLogin: adminLoginMutation.mutateAsync,
    adminLoginPending: adminLoginMutation.isPending,
    logout: () => logoutMutation.mutate(),
    changePassword: changePasswordMutation.mutateAsync,
    changePasswordPending: changePasswordMutation.isPending,
    registerCustomer: registerCustomerMutation.mutateAsync,
    registerCustomerPending: registerCustomerMutation.isPending,
    registerFarmer: registerFarmerMutation.mutateAsync,
    registerFarmerPending: registerFarmerMutation.isPending,
    setRole: (role) => authStoreFor(portal).getState().setRole(role),
  };
}
