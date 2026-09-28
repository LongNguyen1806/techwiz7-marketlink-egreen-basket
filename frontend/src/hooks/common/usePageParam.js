import { useCallback, useEffect } from 'react';

export function readPage(filters) {
  return Math.max(1, Math.floor(Number(filters.page) || 1));
}

export function usePageParam({ filters, setFilters, query }) {
  const page = readPage(filters);

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
