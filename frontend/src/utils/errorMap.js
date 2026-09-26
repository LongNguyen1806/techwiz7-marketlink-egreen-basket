const ERROR_MAP = {
  INSUFFICIENT_STOCK: {
    title: 'Insufficient stock',
    suggestion: 'Reduce the quantity or choose another product.',
  },
  OPEN_ORDER_LIMIT_EXCEEDED: {
    title: 'Open order limit exceeded',
    suggestion: 'Complete or cancel open orders before placing another.',
  },
  SLOT_NOT_AVAILABLE: {
    title: 'Pickup slot is no longer available',
    suggestion: 'Choose another pickup slot.',
  },
  PRODUCT_NOT_AVAILABLE: {
    title: 'Product is no longer available',
    suggestion: 'Remove it from your cart and choose something else.',
  },
  CUTOFF_PASSED: {
    title: 'Order cut-off has passed',
    suggestion: 'Orders cannot be changed after cut-off.',
  },
  IDEMPOTENCY_IN_PROGRESS: {
    title: 'Order is being processed',
    suggestion: 'Please wait a few seconds and try again.',
  },
  RESOURCE_MODIFIED: {
    title: 'Order was just updated',
    suggestion: 'Reload the order to see the latest version.',
  },
  INVALID_STATUS_TRANSITION: {
    title: 'This status change is not allowed',
    suggestion: "Check the order's current status.",
  },
  PICKUP_ALREADY_STARTED: {
    title: 'Pickup time has started',
    suggestion: 'Orders cannot be cancelled or edited after the pickup slot starts.',
  },
  FARMER_SUSPENDED: {
    title: 'Farmer account is temporarily suspended',
  },
  FARMER_NOT_APPROVED: {
    title: 'Farmer profile is not approved yet',
  },
  CUTOFF_NOT_REACHED: {
    title: 'Cut-off has not been reached',
    suggestion: 'Wait until cut-off before marking ready.',
  },
  PICKUP_NOT_ENDED: {
    title: 'Pickup slot has not ended',
    suggestion: 'Complete or mark no-show after the slot ends.',
  },
  REVIEW_NOT_ALLOWED: {
    title: 'Review not allowed yet',
    suggestion: 'You can only review after the order is completed.',
  },
  REPLY_ALREADY_EXISTS: {
    title: 'This review has already been replied to',
  },
  RESOURCE_IN_USE: {
    title: 'Resource is in use',
    suggestion: 'Cannot delete while related data still exists.',
  },
  EMAIL_EXISTS: {
    title: 'Email is already registered',
    suggestion: 'Sign in or use a different email.',
  },
  INVALID_CREDENTIALS: {
    title: 'Incorrect email or password',
  },
  ACCOUNT_LOCKED: {
    title: 'Account is locked',
    suggestion: 'Contact an administrator for help.',
  },
  TOKEN_INVALID: {
    title: 'Session expired',
    suggestion: 'Please sign in again.',
  },
  VALIDATION_ERROR: {
    title: 'Invalid data',
    suggestion: 'Check the fields marked with errors.',
  },
  CONFLICT_RETRY: {
    title: 'Data conflict',
    suggestion: 'Reload and try the action again.',
  },
  OVERDUE_ORDERS_PENDING: {
    title: 'Overdue orders remaining',
    suggestion: 'Resolve all overdue orders before applying the weekly stock template.',
  },
  AI_UNAVAILABLE: {
    title: 'AI assistant is temporarily unavailable',
    suggestion: 'Please try again in a few minutes.',
  },
};

export function mapErrorCode(code) {
  if (!code) {
    return { title: 'Something went wrong', suggestion: 'Please try again.' };
  }
  return (
    ERROR_MAP[code] ?? {
      title: 'Something went wrong',
      suggestion: 'Please try again.',
    }
  );
}

export function getErrorMessage(code, fallback) {
  if (fallback) return fallback;
  return mapErrorCode(code).title;
}
