const NON_FIELD_KEYS = new Set(['non_field_errors', 'detail']);


export function mapServerErrorsToForm(serverErrors, setError, { fields } = {}) {
  if (!serverErrors || !setError) return false;
  const known = fields ? new Set(fields) : null;
  const leftovers = [];
  let mapped = false;

  for (const [field, messages] of Object.entries(serverErrors)) {
    const message = Array.isArray(messages) ? messages[0] : messages;
    if (!message) continue;
    if (NON_FIELD_KEYS.has(field) || (known && !known.has(field.split('.')[0]))) {
      leftovers.push(message);
      continue;
    }
    setError(field, { type: 'server', message }, { shouldFocus: !mapped });
    mapped = true;
  }

  if (leftovers.length > 0) {
    setError('root.server', { type: 'server', message: leftovers.join(' ') });
    mapped = true;
  }
  return mapped;
}


export const formErrorMessage = (apiError) => {
  if (!apiError) return 'An unexpected error occurred.';
  if (apiError.code === 'ACCOUNT_LOCKED') {
    const reason = apiError.fieldErrors?.reason?.[0];
    return reason
      ? `Your account has been locked. Reason: ${reason}. Please contact the administrator.`
      : 'Your account has been locked. Please contact the administrator.';
  }

  return apiError.friendlyMessage || apiError.message || 'An error occurred. Please try again.';
};

