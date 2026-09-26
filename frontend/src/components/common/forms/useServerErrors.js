import { useState } from 'react';
import { ApiError } from '../../../lib/ApiError';
import { formErrorMessage, mapServerErrorsToForm } from '../../../utils/mapServerErrors';

/**
 * Turn a rejected request into something the form can show: field messages under their own inputs,
 * and one sentence at the top for everything else.
 *
 * @param {string[]} fields the names this form renders; anything else would be set and never seen.
 */
export function useServerErrors(fields) {
  const [formError, setFormError] = useState(null);

  return {
    formError,
    clear: () => setFormError(null),
    report: (error, setError) => {
      const apiError = ApiError.fromUnknown(error);
      const mapped = mapServerErrorsToForm(apiError.fieldErrors, setError, fields);
      setFormError(mapped ? null : formErrorMessage(apiError));
    },
  };
}
