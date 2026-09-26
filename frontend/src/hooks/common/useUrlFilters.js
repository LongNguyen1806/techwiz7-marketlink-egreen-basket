import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';

export const PAGE_PARAM = 'page';

function coerce(raw, fallback) {
  if (typeof fallback === 'number') {
    const value = Number(raw);
    return Number.isFinite(value) ? value : fallback;
  }
  if (typeof fallback === 'boolean') return raw === 'true';
  return raw;
}

/**
 * Filters kept in the URL query string, so refresh, Back and shared links keep them.
 * `defaults` lists every filter with its default; a filter at its default is left out of
 * the URL. Changing any filter other than the page goes back to page 1.
 *
 *   const { filters, setFilters } = useUrlFilters({ tab: 'placed', page: 1 });
 *   setFilters({ tab: 'accepted' });
 */
export function useUrlFilters(defaults) {
  const [searchParams, setSearchParams] = useSearchParams();
  // Callers pass an object literal; compare by content, not identity.
  const defaultsKey = JSON.stringify(defaults);

  const filters = useMemo(() => {
    const base = JSON.parse(defaultsKey);
    const values = {};
    for (const [key, fallback] of Object.entries(base)) {
      const raw = searchParams.get(key);
      values[key] = raw === null ? fallback : coerce(raw, fallback);
    }
    return values;
  }, [searchParams, defaultsKey]);

  const setFilters = useCallback(
    (patch, { replace = false } = {}) => {
      const base = JSON.parse(defaultsKey);
      setSearchParams(
        (previous) => {
          const next = new URLSearchParams(previous);
          for (const [key, value] of Object.entries(patch)) {
            if (value === undefined || value === null || value === '' || value === base[key]) {
              next.delete(key);
            } else {
              next.set(key, String(value));
            }
          }
          if (!(PAGE_PARAM in patch)) next.delete(PAGE_PARAM);
          return next;
        },
        { replace },
      );
    },
    [defaultsKey, setSearchParams],
  );

  const resetFilters = useCallback(() => {
    const base = JSON.parse(defaultsKey);
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        Object.keys(base).forEach((key) => next.delete(key));
        return next;
      },
      { replace: true },
    );
  }, [defaultsKey, setSearchParams]);

  return { filters, setFilters, resetFilters };
}
