import { useState } from 'react';
import { ApiError } from '../../../lib/ApiError';
import { formErrorMessage, mapServerErrorsToForm } from '../../../utils/mapServerErrors';


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
