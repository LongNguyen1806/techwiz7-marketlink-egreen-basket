const NON_FIELD_KEYS = new Set(['non_field_errors', 'detail']);

/**
 * Puts backend field errors ({ field: [messages] }) onto React Hook Form fields.
 * Dotted paths from the backend ("items.0.quantity") match RHF paths as they are.
 *
 * `fields` limits mapping to fields the form actually renders; anything else, and
 * non-field errors, go to `root.server` so the form can still show them.
 * Returns true when at least one message was placed.
 */
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
