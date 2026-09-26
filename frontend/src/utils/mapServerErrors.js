/** Map backend `errors` object onto React Hook Form fields. */
export const mapServerErrorsToForm = (serverErrors, setError) => {
  if (!serverErrors || !setError) return;
  Object.keys(serverErrors).forEach((field) => {
    const message = serverErrors[field]?.[0];
    if (message) {
      setError(field, { type: 'server', message });
    }
  });
};
