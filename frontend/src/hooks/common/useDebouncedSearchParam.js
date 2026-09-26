import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { SEARCH_DEBOUNCE_MS, useDebouncedValue } from './useDebouncedValue';
import { PAGE_PARAM } from './useUrlFilters';

/**
 * A search box backed by a URL query parameter.
 *
 * The input updates on every keystroke; the URL (and so the query built from `term`)
 * only changes after typing pauses for `delay` ms. Enter or the clear button apply at
 * once. A new term goes back to page 1, and URL updates use replace so typing does not
 * fill the Back history.
 *
 *   const search = useDebouncedSearchParam('q');
 *   <Input value={search.value} onChange={search.onChange} onKeyDown={search.onKeyDown} />
 *   useFarmerOrders({ ...filters, q: search.term || undefined });
 */
export function useDebouncedSearchParam(key = 'q', { delay = SEARCH_DEBOUNCE_MS } = {}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const term = searchParams.get(key) ?? '';
  const [value, setValue] = useState(term);
  const debounced = useDebouncedValue(value.trim(), delay);
  const lastCommitted = useRef(term);

  // The URL changed from outside (Back/Forward, a link): show that term in the box.
  useEffect(() => {
    if (term !== lastCommitted.current) {
      lastCommitted.current = term;
      setValue(term);
    }
  }, [term]);

  const commit = useCallback(
    (next) => {
      if (next === lastCommitted.current) return;
      lastCommitted.current = next;
      setSearchParams(
        (previous) => {
          const params = new URLSearchParams(previous);
          if (next) params.set(key, next);
          else params.delete(key);
          params.delete(PAGE_PARAM);
          return params;
        },
        { replace: true },
      );
    },
    [key, setSearchParams],
  );

  useEffect(() => {
    commit(debounced);
  }, [debounced, commit]);

  const onChange = useCallback((event) => setValue(event.target.value), []);

  const flush = useCallback(() => commit(value.trim()), [commit, value]);

  const clear = useCallback(() => {
    setValue('');
    commit('');
  }, [commit]);

  const onKeyDown = useCallback(
    (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        flush();
      } else if (event.key === 'Escape' && value) {
        clear();
      }
    },
    [clear, flush, value],
  );

  return {
    value,
    setValue,
    onChange,
    onKeyDown,
    flush,
    clear,
    // The applied term; build queries from this, not from `value`.
    term,
    // Typing has not been applied yet.
    isDebouncing: value.trim() !== term,
  };
}
