import { useCallback, useEffect, useRef } from 'react';
import { useBlocker } from 'react-router-dom';

/**
 * Warns before leaving a form with unsaved changes: in-app navigation is held by the
 * returned blocker (render a confirm dialog while blocker.state === 'blocked'), and
 * closing or reloading the tab gets the browser's own prompt.
 * Call allowNavigation() right before navigating away after a successful save.
 */
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
