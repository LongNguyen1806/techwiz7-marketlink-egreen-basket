const SECOND = 1000;
const MINUTE = 60 * SECOND;



export const STALE = Object.freeze({
  
  SEARCH: 0,
  
  LIVE: 0,
  SHORT: 30 * SECOND,
  MINUTE,
  MEDIUM: 5 * MINUTE,
  LONG: 10 * MINUTE,
  
  STATIC: 30 * MINUTE,
  
  SESSION: Infinity,
});

export const NOTIFICATION_POLL_INTERVAL = 30 * SECOND;
