import { toast } from 'sonner';

import { ApiError } from '@/lib/ApiError';

export { toast };

export function notify(message, description) {
  toast.success(message, description ? { description } : undefined);
}

/**
 * Report a failed request once, in words.
 *
 * Field errors are deliberately silent: a 400 that names its fields is already being drawn
 * next to those fields, and a toast saying the same thing is noise the form has to apologise
 * for twice.
 */
export function notifyError(error, override) {
  const apiError = ApiError.fromUnknown(error);
  if (!override && Object.keys(apiError.fieldErrors).length > 0) return;
  toast.error(override ?? apiError.friendlyMessage);
}
