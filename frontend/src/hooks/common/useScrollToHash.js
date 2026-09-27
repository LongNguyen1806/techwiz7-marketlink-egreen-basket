import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

/** Scroll to the element named in the URL hash (/about#faq, /privacy#retention) once it exists. */
export function useScrollToHash(ready = true) {
  const { hash } = useLocation();
  useEffect(() => {
    if (!hash || !ready) return;
    const target = document.getElementById(decodeURIComponent(hash.slice(1)));
    target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [hash, ready]);
  return hash.slice(1);
}
