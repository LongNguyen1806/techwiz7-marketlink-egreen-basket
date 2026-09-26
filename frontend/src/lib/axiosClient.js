import axios from 'axios';
import { env } from '../config/env';
import { selectIsAuthenticated, useAuthStore } from '../stores/auth.store';
import { CLIENT_ERROR_CODES } from '../utils/errorMap';
import { ApiError } from './ApiError';
import { notifyError } from './toast';

/*
 * Per-request options on top of axios:
 *   signal      pass React Query's AbortSignal so a superseded request is cancelled
 *   ifMatch     order/resource version, sent as If-Match (optimistic locking, 409 on mismatch)
 *   idempotent  adds an Idempotency-Key that stays the same if the request is replayed
 */
const axiosClient = axios.create({
  baseURL: env.API_BASE_URL,
  headers: { Accept: 'application/json' },
});

// A 401 from these means wrong credentials or a dead refresh token, not an expired access token.
const NO_REFRESH_PATHS = ['/auth/login/', '/auth/admin/login/', '/auth/refresh/'];

function isNoRefreshPath(url = '') {
  return NO_REFRESH_PATHS.some((path) => url.endsWith(path));
}

// crypto.randomUUID only exists in secure contexts; the dev server is also opened over
// plain http on the LAN, so fall back to getRandomValues.
function uuidV4() {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function isEnvelope(body) {
  return body !== null && typeof body === 'object' && !(body instanceof Blob) && 'success' in body && 'data' in body;
}

// Used when the response has no envelope (e.g. the dev proxy cannot reach Django).
function codeForBareStatus(status) {
  if (status === 401) return 'NOT_AUTHENTICATED';
  if (status === 403) return 'PERMISSION_DENIED';
  if (status === 404) return 'NOT_FOUND';
  if (status === 429) return 'THROTTLED';
  if (status === 502 || status === 503 || status === 504) return CLIENT_ERROR_CODES.NETWORK_ERROR;
  if (status >= 500) return 'INTERNAL_SERVER_ERROR';
  return CLIENT_ERROR_CODES.UNKNOWN;
}

async function toApiError(error) {
  const { response } = error;
  if (!response) {
    return new ApiError({ status: 0, code: CLIENT_ERROR_CODES.NETWORK_ERROR, message: error.message });
  }
  let body = response.data;
  // A failed blob download still carries the JSON error envelope.
  if (body instanceof Blob) {
    try {
      body = JSON.parse(await body.text());
    } catch {
      body = null;
    }
  }
  const envelope = isEnvelope(body) ? body : null;
  return new ApiError({
    status: response.status,
    code: envelope?.code ?? codeForBareStatus(response.status),
    message: envelope?.message ?? '',
    fieldErrors: envelope?.errors,
    data: envelope?.data,
    requestId: envelope?.request_id ?? null,
  });
}

// Ends a session the server no longer accepts. Clearing the store sends guarded pages to
// /login and empties the query cache (see useAuthSessionSync).
function expireSession() {
  if (!selectIsAuthenticated(useAuthStore.getState())) return;
  useAuthStore.getState().clearSession();
  notifyError(new ApiError({ status: 401, code: CLIENT_ERROR_CODES.SESSION_EXPIRED }));
}

// Refresh tokens rotate, so concurrent 401s must share one refresh call.
let refreshPromise = null;

function refreshAccessToken() {
  if (!refreshPromise) {
    const { refreshToken } = useAuthStore.getState();
    refreshPromise = axios
      .post(`${env.API_BASE_URL}/auth/refresh/`, { refresh: refreshToken })
      .then(({ data: envelope }) => {
        const { access, refresh } = envelope.data;
        useAuthStore.getState().setTokens({ access, refresh });
        return access;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

axiosClient.interceptors.request.use((config) => {
  const { accessToken } = useAuthStore.getState();
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  if (config.ifMatch !== undefined && config.ifMatch !== null) {
    config.headers['If-Match'] = `"${config.ifMatch}"`;
  }
  if (config.idempotent && !config.headers['Idempotency-Key']) {
    config.headers['Idempotency-Key'] = uuidV4();
  }
  return config;
});

axiosClient.interceptors.response.use(
  (response) => {
    // Unwrap { success, message, data, errors }: callers read response.data as the payload.
    if (isEnvelope(response.data)) {
      response.envelope = response.data;
      response.data = response.data.data;
    }
    return response;
  },
  async (error) => {
    // Let React Query see its own cancellations untouched.
    if (axios.isCancel(error)) throw error;

    const { config, response } = error;
    const canRefresh =
      response?.status === 401 &&
      config &&
      !config._retried &&
      !isNoRefreshPath(config.url) &&
      useAuthStore.getState().refreshToken;

    if (canRefresh) {
      config._retried = true;
      try {
        const access = await refreshAccessToken();
        config.headers.Authorization = `Bearer ${access}`;
        return axiosClient(config);
      } catch {
        expireSession();
        throw new ApiError({ status: 401, code: CLIENT_ERROR_CODES.SESSION_EXPIRED });
      }
    }

    const apiError = await toApiError(error);
    // Still refused after a refresh, or the account was locked while signed in.
    if ((apiError.status === 401 && !isNoRefreshPath(config?.url)) || apiError.is('ACCOUNT_LOCKED')) {
      expireSession();
    }
    throw apiError;
  },
);

export default axiosClient;
