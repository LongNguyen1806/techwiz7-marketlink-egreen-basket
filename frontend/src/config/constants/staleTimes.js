const SECOND = 1000;
const MINUTE = 60 * SECOND;

/**
 * How long a cached answer may be served before it is refetched.
 *
 * Named rather than written inline so that "this list is being moderated" and "this list
 * barely changes" are visibly different decisions instead of two magic numbers.
 */
export const STALE = Object.freeze({
  // A search or a moderation list: always ask, never show yesterday's answer.
  LIVE: 0,
  SEARCH: 0,
  SHORT: 30 * SECOND,
  MINUTE,
  MEDIUM: 5 * MINUTE,
  LONG: 10 * MINUTE,
  // Categories, markets, platform limits.
  STATIC: 30 * MINUTE,
  // The signed-in user: it changes only when the session does, and the session says so.
  SESSION: Infinity,
});

export const NOTIFICATION_POLL_INTERVAL = 30 * SECOND;
