import { useEffect, useState } from 'react';

/**
 * The current time as state, so a screen that depends on it re-renders when it moves.
 *
 * Reading the clock during render would freeze the value at the first paint: a pickup window whose
 * cut-off passes while C-02 sits open would stay selectable (D-007).
 */
export function useNow(intervalMs = 30_000) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs]);

  return now;
}
