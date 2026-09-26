import { toast } from 'sonner';
import { hasErrorMessage } from '../utils/errorMap';
import { ApiError } from './ApiError';

const DURATION = {
  success: 3000,
  info: 4000,
  warning: 5000,
  error: 6000,
};

export const notify = {
  success: (title, options) => toast.success(title, { duration: DURATION.success, ...options }),
  info: (title, options) => toast.info(title, { duration: DURATION.info, ...options }),
  warning: (title, options) => toast.warning(title, { duration: DURATION.warning, ...options }),
  error: (title, options) => toast.error(title, { duration: DURATION.error, ...options }),
  dismiss: (id) => toast.dismiss(id),
};

export function notifyError(error, override = {}) {
  const apiError = ApiError.fromUnknown(error);
  const friendly = apiError.friendly;

  if (import.meta.env.DEV && !hasErrorMessage(apiError.code)) {
    console.warn('[api] unmapped error', {
      code: apiError.code,
      status: apiError.status,
      message: apiError.apiMessage,
      requestId: apiError.requestId,
    });
  }

  const description = override.description ?? friendly.description;
  const reference = apiError.isServerError && apiError.requestId ? ` Reference: ${apiError.requestId}` : '';

  return notify.error(override.title ?? friendly.title, {
    id: `error:${apiError.code}`,
    description: `${description}${reference}`,
  });
}
