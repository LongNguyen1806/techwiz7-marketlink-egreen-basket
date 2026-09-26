import { useCallback, useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import useWebSocket, { ReadyState } from 'react-use-websocket';
import { authApi } from '../../api/common/authApi';
import { env } from '../../config/env';
import { queryKeysForNotification } from '../../constants/notificationEvents';
import { authKeys } from '../../constants/queryKeys';
import { notify } from '../../lib/toast';
import { selectIsAuthenticated, useAuthStore } from '../../stores/auth.store';
import { useUiStore } from '../../stores/ui.store';

// notifications/consumers.py closes with 4401 after logout, account lock or a bad ticket.
const CLOSE_UNAUTHORIZED = 4401;
const MAX_RECONNECT_DELAY_MS = 30_000;

/**
 * Realtime notifications. Mount once per signed-in layout.
 *
 * Every (re)connect asks for a fresh single-use ticket. Each pushed notification refreshes
 * the queries it affects (constants/notificationEvents.js) and shows a toast. While the
 * socket is down, notification queries fall back to polling (see ui.store realtimeConnected).
 */
export function useNotificationSocket({ enabled = true } = {}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const isAuthenticated = useAuthStore(selectIsAuthenticated);
  const setRealtimeConnected = useUiStore((state) => state.setRealtimeConnected);
  const hasConnectedBefore = useRef(false);

  const getSocketUrl = useCallback(async () => {
    const { ticket } = await authApi.wsTicket();
    return `${env.WS_BASE_URL}/notifications/?ticket=${encodeURIComponent(ticket)}`;
  }, []);

  const handleMessage = useCallback(
    (event) => {
      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch {
        return;
      }
      if (payload?.event !== 'NEW_NOTIFICATION' || !payload.data) return;

      const item = payload.data;
      queryKeysForNotification(item.type).forEach((queryKey) => {
        void queryClient.invalidateQueries({ queryKey });
      });
      notify.info(item.title, {
        id: `notification:${item.id}`,
        description: item.message,
        action: item.target_url ? { label: 'View', onClick: () => navigate(item.target_url) } : undefined,
      });
    },
    [navigate, queryClient],
  );

  const { readyState } = useWebSocket(enabled && isAuthenticated ? getSocketUrl : null, {
    shouldReconnect: (event) => event.code !== CLOSE_UNAUTHORIZED,
    reconnectAttempts: 20,
    reconnectInterval: (attempt) => Math.min(1000 * 2 ** attempt, MAX_RECONNECT_DELAY_MS),
    retryOnError: true,
    onMessage: handleMessage,
    onOpen: () => {
      // Events sent while we were offline are lost; catch up on reconnect.
      if (hasConnectedBefore.current) void queryClient.invalidateQueries();
      hasConnectedBefore.current = true;
    },
    onClose: (event) => {
      // Refused: check whether the session itself is still valid (a 401 here ends it).
      if (event.code === CLOSE_UNAUTHORIZED) void queryClient.invalidateQueries({ queryKey: authKeys.me() });
    },
  });

  useEffect(() => {
    setRealtimeConnected(readyState === ReadyState.OPEN);
  }, [readyState, setRealtimeConnected]);

  useEffect(() => () => setRealtimeConnected(false), [setRealtimeConnected]);

  return { readyState, isConnected: readyState === ReadyState.OPEN };
}
