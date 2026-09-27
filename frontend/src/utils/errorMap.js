





export const CLIENT_ERROR_CODES = Object.freeze({
  NETWORK_ERROR: 'NETWORK_ERROR',
  SESSION_EXPIRED: 'SESSION_EXPIRED',
  UNKNOWN: 'UNKNOWN',
});

const ERROR_MESSAGES = {
  
  VALIDATION_ERROR: {
    title: 'Some details need your attention',
    description: 'Please check the highlighted fields and try again.',
  },
  EMAIL_EXISTS: {
    title: 'This email is already registered',
    description: 'Sign in instead, or use a different email address.',
  },
  INSUFFICIENT_STOCK: {
    title: 'Not enough stock',
    description: 'Lower the quantity or choose another product.',
  },
  INVALID_STATUS_TRANSITION: {
    title: 'This action is no longer possible',
    description: 'The status has changed in the meantime. Refresh to see the latest state.',
  },

  
  NOT_AUTHENTICATED: {
    title: 'Please sign in to continue',
    description: 'Your session may have ended.',
  },
  INVALID_CREDENTIALS: {
    title: 'Incorrect email or password',
    description: 'Check your details and try again.',
  },
  TOKEN_INVALID: {
    title: 'Your session has expired',
    description: 'Please sign in again.',
  },

  
  ACCOUNT_LOCKED: {
    title: 'This account is locked',
    description: 'Contact MarketLink support for help.',
  },
  PERMISSION_DENIED: {
    title: "You don't have access to this",
    description: "This action isn't available for your account.",
  },
  ACTION_NOT_PERMITTED_FOR_ROLE: {
    title: "This isn't available for your account type",
    description: 'Sign in with the right account to continue.',
  },
  FARMER_NOT_APPROVED: {
    title: "Your stall isn't approved yet",
    description: 'You can make changes once an administrator approves your stall.',
  },
  FARMER_SUSPENDED: {
    title: 'Your stall is suspended',
    description: 'Changes are paused while your stall is suspended. Contact support for details.',
  },

  
  NOT_FOUND: {
    title: "We couldn't find that",
    description: 'It may have been removed, or the link is out of date.',
  },

  
  RESOURCE_MODIFIED: {
    title: 'This was just updated',
    description: 'Someone else changed it a moment ago. Review the latest version and try again.',
  },
  IDEMPOTENCY_IN_PROGRESS: {
    title: 'Your request is still being processed',
    description: 'Please wait a moment before trying again.',
  },
  CONFLICT_RETRY: {
    title: 'Something else changed at the same time',
    description: 'Please try again.',
  },

  
  OPEN_ORDER_LIMIT_EXCEEDED: {
    title: "You've reached the limit of open orders",
    description: 'Complete or cancel an open order before placing a new one.',
  },
  CUTOFF_PASSED: {
    title: 'The order cut-off has passed',
    description: 'This order can no longer be changed.',
  },
  CUTOFF_NOT_REACHED: {
    title: "It's too early for this step",
    description: 'You can mark the order ready once its cut-off time has passed.',
  },
  PICKUP_ALREADY_STARTED: {
    title: 'The pickup window has already started',
    description: 'This order can no longer be changed or declined.',
  },
  PICKUP_NOT_ENDED: {
    title: "The pickup window hasn't ended yet",
    description: 'You can mark a no-show once the pickup window is over.',
  },
  SLOT_NOT_AVAILABLE: {
    title: 'That pickup slot is no longer available',
    description: 'Please choose another pickup slot.',
  },
  PRODUCT_NOT_AVAILABLE: {
    title: 'This product is no longer available',
    description: 'Remove it and choose something else.',
  },
  REVIEW_NOT_ALLOWED: {
    title: "This review can't be posted",
    description: 'Reviews open once an order is completed.',
  },
  REPLY_ALREADY_EXISTS: {
    title: 'This review already has a reply',
    description: 'Each review can be answered once.',
  },
  RESOURCE_IN_USE: {
    title: 'This is still in use',
    description: 'Remove what depends on it first, then try again.',
    serverDetail: true,
  },
  IDEMPOTENCY_KEY_REUSED: {
    title: 'This request was already submitted',
    description: 'Refresh the page to see its result.',
  },
  FAILED_PRECONDITION: {
    title: "This can't be done right now",
    description: 'Some conditions are not met yet. Refresh and try again.',
    serverDetail: true,
  },

  
  PRECONDITION_REQUIRED: {
    title: "We couldn't confirm the latest version",
    description: 'Refresh the page and try again.',
  },

  
  THROTTLED: {
    title: 'Too many attempts',
    description: 'Please wait a few minutes before trying again.',
  },

  
  INTERNAL_SERVER_ERROR: {
    title: 'Something went wrong on our side',
    description: 'Please try again in a moment.',
  },
  AI_UNAVAILABLE: {
    title: 'The assistant is temporarily unavailable',
    description: 'Please try again in a few minutes.',
  },

  
  NETWORK_ERROR: {
    title: "Can't reach the server",
    description: 'Check your internet connection and try again.',
  },
  SESSION_EXPIRED: {
    title: 'Your session has expired',
    description: 'Please sign in again to continue.',
  },
  UNKNOWN: {
    title: 'Something went wrong',
    description: 'Please try again.',
  },
};


export function describeError(error) {
  const code = error?.code;
  const entry = ERROR_MESSAGES[code] ?? ERROR_MESSAGES.UNKNOWN;
  const serverMessage = typeof error?.apiMessage === 'string' ? error.apiMessage : error?.message;
  const description = entry.serverDetail && serverMessage ? serverMessage : entry.description;
  return { title: entry.title, description };
}

export function hasErrorMessage(code) {
  return Boolean(code && ERROR_MESSAGES[code]);
}


export function getErrorMessage(code) {
  return (ERROR_MESSAGES[code] ?? ERROR_MESSAGES.UNKNOWN).title;
}


export function mapErrorCode(code) {
  const entry = ERROR_MESSAGES[code] ?? ERROR_MESSAGES.UNKNOWN;
  return { title: entry.title, suggestion: entry.description };
}
