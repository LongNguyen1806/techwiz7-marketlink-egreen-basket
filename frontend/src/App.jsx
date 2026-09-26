import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from 'react-router-dom';
import { Toaster } from 'sonner';
import { CircleCheck, CircleX, Info, TriangleAlert } from 'lucide-react';
import { ErrorBoundary } from './components/feedback/ErrorBoundary';
import { TooltipProvider } from './components/ui/Tooltip';
import { useAuthSessionSync } from './hooks/authentication/useAuth';
import { queryClient } from './lib/queryClient';
import { router } from './router/AppRouter';


const TOAST_ICONS = {
  success: <CircleCheck size={18} />,
  error: <CircleX size={18} />,
  warning: <TriangleAlert size={18} />,
  info: <Info size={18} />,
};

function SessionSync() {
  useAuthSessionSync();
  return null;
}

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider delayDuration={200}>
          <SessionSync />
          <RouterProvider router={router} />
          <Toaster position="bottom-left" richColors closeButton visibleToasts={4} icons={TOAST_ICONS} />
        </TooltipProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
