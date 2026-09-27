import { useEffect, useState } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from 'react-router-dom';
import { createPortal } from 'react-dom';
import { Toaster } from 'sonner';

import { authApi } from './api/common/authApi';
import { catalogApi } from './api/guest/catalogApi';
import { AiChatWidget } from '@/components/common/chat/AiChatWidget';
import { ErrorBoundary } from '@/components/common/feedback/ErrorBoundary';
import { PageSkeleton } from '@/components/common/feedback/PageSkeleton';
import { TooltipProvider } from '@/components/common/layout/Tooltip';
import { QUERY_KEYS } from '@/config/constants';
import { env } from '@/config/env';
import { queryClient } from '@/lib/queryClient';
import { router } from './router/AppRouter';
import {
  authStoreFor,
  currentPortal,
  hasHydrated,
  onHydrated,
  selectIsAuthenticated,
} from '@/stores/auth.store';

let mockingStarted = false;

async function enableMocking() {
  if (!env.USE_MOCK || mockingStarted) return;
  const { worker } = await import('@/mocks/browser');
  await worker.start({
    onUnhandledRequest: 'bypass',
    quiet: true,
  });
  mockingStarted = true;
}

// Both portals, because either may hold a session from a previous visit and the boot below
// has to know which one this page belongs to before it asks who is signed in.
function waitForAuthHydration() {
  if (hasHydrated()) return Promise.resolve();
  return new Promise((resolve) => {
    const unsubscribe = onHydrated(() => {
      unsubscribe();
      resolve();
    });
  });
}

const LOGIN_PATH = { market: '/login', admin: '/admin/login' };

function BootProvider({ children }) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // The event names the portal whose session expired. Only that portal's viewer is sent to
    // a login screen; a tab showing the other one carries on.
    const onLost = (event) => {
      const portal = event.detail?.portal ?? currentPortal();
      if (portal !== currentPortal()) return;
      queryClient.clear();
      const loginPath = LOGIN_PATH[portal] ?? LOGIN_PATH.market;
      if (window.location.pathname !== loginPath) {
        window.location.assign(loginPath);
      }
    };
    window.addEventListener('auth:session-lost', onLost);
    return () => window.removeEventListener('auth:session-lost', onLost);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      await waitForAuthHydration();
      await enableMocking();

      try {
        const config = await catalogApi.getConfig();
        if (!cancelled) {
          queryClient.setQueryData(QUERY_KEYS.PUBLIC_CONFIG, config);
        }
      } catch {
        // Config is non-blocking for Phase 1 shell.
      }

      // Only the portal this page belongs to is resumed. Asking the API who the *other*
      // portal's token belongs to would spend a request on a session nothing here can use.
      const portal = currentPortal();
      const store = authStoreFor(portal);

      if (selectIsAuthenticated(store.getState())) {
        try {
          const me = await authApi.me();
          if (!cancelled) {
            queryClient.setQueryData(QUERY_KEYS.ME(portal), me);
            store.getState().setRole(me.role);
          }
        } catch {
          if (!cancelled) store.getState().clearSession();
        }
      }

      if (!cancelled) setReady(true);
    }

    void boot();
    return () => {
      cancelled = true;
    };
    // Boot runs once. The stores it touches are read through getState(), not through a
    // subscription, so there is nothing here that could change and warrant a second run.
  }, []);

  if (!ready) {
    return <PageSkeleton />;
  }

  return children;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={200}>
        <BootProvider>
          <ErrorBoundary>
            <RouterProvider router={router} />
          </ErrorBoundary>
          <AiChatWidget />
          {/* reset.css gives #root `isolation: isolate`, so everything rendered inside it is
              trapped below the Sheet / Dialog overlays that Radix portals to <body> - the
              toast ended up behind a blurred, dimmed backdrop. Portalling it to <body> too
              puts it back in the same stacking context, where its own z-index wins. */}
          {createPortal(
            <Toaster richColors position="bottom-left" closeButton />,
            document.body,
          )}
        </BootProvider>
      </TooltipProvider>
    </QueryClientProvider>
  );
}
