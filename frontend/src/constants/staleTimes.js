const SECOND = 1000;
const MINUTE = 60 * SECOND;

// staleTime only decides whether mounting / refocusing refetches. Mutations and realtime
// events still refresh data through invalidateQueries, whatever the value here.
export const STALE = Object.freeze({
  // Search and filter results: show the cache instantly, always revalidate in the background.
  SEARCH: 0,
  // Data an action depends on right now (order version for If-Match, stock before apply).
  LIVE: 0,
  SHORT: 30 * SECOND,
  MINUTE,
  MEDIUM: 5 * MINUTE,
  LONG: 10 * MINUTE,
  // Admin-managed reference data (categories, public config).
  STATIC: 30 * MINUTE,
  // Changes only through login, logout or the user's own edits.
  SESSION: Infinity,
});

export const NOTIFICATION_POLL_INTERVAL = 30 * SECOND;
