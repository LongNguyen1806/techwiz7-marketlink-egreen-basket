import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useLocation } from 'react-router-dom';
import { toast } from 'sonner';

import { authApi } from '../../../api/common/authApi';
import { adaptNotification } from '@/lib/adapters/notification.adapter';
import { QUERY_KEYS } from '@/config/constants';
import { env, wsUrl } from '@/config/env';
import { authStoreFor, currentPortal, portalForPath } from '@/stores/auth.store';

function isWsEnvelope(value) {
  if (!value || typeof value !== 'object') return false;
  if (!('event' in value) || !('data' in value)) return false;
  return typeof value.event === 'string';
}

function isBeNotification(value) {
  if (!value || typeof value !== 'object') return false;
  if (!('id' in value)) return false;
  return typeof value.id === 'number';
}

async function pushMockNotification(item) {
  const role = authStoreFor(currentPortal()).getState().role;
  if (role === 'FARMER') {
    const { farmerNotifications } = await import('@/mocks/farmerData');
    farmerNotifications.unshift(item);
    return;
  }
  const { customerNotifications } = await import('@/mocks/orders');
  customerNotifications.unshift(item);
}

/**
 * Prefers WebSocket /ws/notifications/?ticket=…
 * When WS is unavailable (empty BE routing), silently falls back to HTTP
 * short-polling every 30s without noisy reconnect loops.
 */
export function useNotificationSocket(enabled) {
  const queryClient = useQueryClient();
  // The socket ticket is cut from the session of the portal being viewed, so an admin tab
  // does not open a shopper's notification stream. Read from the router rather than from
  // window.location: navigating inside the app changes the portal without a page load, and a
  // location read during render would never hear about it.
  const portal = portalForPath(useLocation().pathname);
  const accessToken = authStoreFor(portal)((s) => s.accessToken);

  useEffect(() => {
    if (!enabled || !accessToken) return;

    let cancelled = false;
    let mockTimer;
    let pollTimer;
    let socket = null;
    let polling = false;

    const invalidate = () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.NOTIFICATIONS_LIST });
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.CUSTOMER_DASHBOARD });
      void queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.FARMER_DASHBOARD()[0]],
      });
    };

    const handleNotification = (item) => {
      toast.message(item.title, { description: item.message });
      invalidate();
    };

    const startPolling = () => {
      if (polling || cancelled) return;
      polling = true;
      invalidate();
      pollTimer = setInterval(() => {
        if (!cancelled) invalidate();
      }, 30_000);
    };

    async function connect() {
      if (polling || cancelled) return;

      if (env.USE_MOCK) {
        invalidate();
        mockTimer = setInterval(() => {
          if (cancelled) return;
          const item = {
            id: Date.now(),
            type: 'ORDER_PLACED',
            title: 'Order update',
            message: 'There is a new change on your order (mock realtime).',
            target_url: null,
            is_read: false,
            read_at: null,
            created_at: new Date().toISOString(),
          };
          void pushMockNotification(item).then(() => {
            if (!cancelled) handleNotification(item);
          });
        }, 45_000);
        return;
      }

      try {
        const ticketResponse = await authApi.wsTicket();
        if (cancelled) return;

        if (!ticketResponse?.ticket) {
          startPolling();
          return;
        }

        const url = wsUrl(
          `/notifications/?ticket=${encodeURIComponent(ticketResponse.ticket)}`,
        );
        socket = new WebSocket(url);

        socket.onopen = () => {
          invalidate();
        };

        socket.onmessage = (event) => {
          try {
            const parsed = JSON.parse(String(event.data));
            if (!isWsEnvelope(parsed)) return;
            if (parsed.event === 'NEW_NOTIFICATION') {
              if (!isBeNotification(parsed.data)) return;
              handleNotification(adaptNotification(parsed.data));
            }
          } catch {
            // Ignore malformed payloads.
          }
        };

        socket.onclose = () => {
          socket = null;
          startPolling();
        };

        socket.onerror = () => {
          try {
            socket?.close();
          } catch {
            // Ignore close errors when the socket never opened.
          }
        };
      } catch {
        startPolling();
      }
    }

    void connect();

    return () => {
      cancelled = true;
      if (mockTimer) clearInterval(mockTimer);
      if (pollTimer) clearInterval(pollTimer);
      if (socket) {
        socket.onclose = null;
        socket.onerror = null;
        try {
          socket.close();
        } catch {
          // Ignore.
        }
      }
    };
  }, [enabled, accessToken, queryClient]);
}
