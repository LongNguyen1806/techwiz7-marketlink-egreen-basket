import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { SEARCH_DEBOUNCE_MS, useDebouncedValue } from './useDebouncedValue';
import { PAGE_PARAM } from './useUrlFilters';


export function useDebouncedSearchParam(key = 'q', { delay = SEARCH_DEBOUNCE_MS } = {}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const term = searchParams.get(key) ?? '';
  const [value, setValue] = useState(term);
  const debounced = useDebouncedValue(value.trim(), delay);
  const lastCommitted = useRef(term);

  
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
    
    term,
    
    isDebouncing: value.trim() !== term,
  };
}
