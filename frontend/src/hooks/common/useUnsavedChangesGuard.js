import { useCallback, useEffect, useRef } from 'react';
import { useBlocker } from 'react-router-dom';


export function useUnsavedChangesGuard(isDirty) {
  const allowed = useRef(false);

  const blocker = useBlocker(
    useCallback(
      ({ currentLocation, nextLocation }) =>
        isDirty && !allowed.current && currentLocation.pathname !== nextLocation.pathname,
      [isDirty],
    ),
  );

  useEffect(() => {
    if (!isDirty) return undefined;
    const onBeforeUnload = (event) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [isDirty]);

  const allowNavigation = useCallback(() => {
    allowed.current = true;
  }, []);

  return { blocker, allowNavigation };
}
