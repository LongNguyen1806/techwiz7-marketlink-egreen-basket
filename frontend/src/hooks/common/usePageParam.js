import { useCallback, useEffect } from 'react';

/** The page number from filters read by useUrlFilters with `page: 1` among its defaults. */
export function readPage(filters) {
  return Math.max(1, Math.floor(Number(filters.page) || 1));
}

/**
 * The page buttons of a paged list whose page lives in the URL. Changing any other filter
 * already drops it back to page 1 (useUrlFilters); this handles going to a page and the
 * case of a page that no longer exists.
 */
export function usePageParam({ filters, setFilters, query }) {
  const page = readPage(filters);

  // An old link, or the last row of the last page archived: the API answers 404 for a page
  // past the end, so go back to the first one instead of showing an error.
  const pageMissing = page > 1 && query.isError && query.error?.status === 404;
  useEffect(() => {
    if (pageMissing) setFilters({ page: 1 }, { replace: true });
  }, [pageMissing, setFilters]);

  return useCallback(
    (next) => {
      setFilters({ page: next });
      window.scrollTo({ top: 0, behavior: 'smooth' });
    },
    [setFilters],
  );
}
