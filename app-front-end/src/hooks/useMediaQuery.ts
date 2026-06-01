import { useState, useEffect } from 'react';

/**
 * Returns true when the viewport matches the given media query.
 */
export function useMediaQuery(query: string): boolean {
  // Initialize synchronously from the real viewport so the first paint already
  // matches the correct breakpoint. Defaulting to `false` caused mobile-only
  // chrome to flash for one frame before the effect corrected it.
  const [matches, setMatches] = useState(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false;
    return window.matchMedia(query).matches;
  });

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) {
      setMatches(false);
      return;
    }
    const m = window.matchMedia(query);
    setMatches(m.matches);
    const handler = (e: MediaQueryListEvent) => setMatches(e.matches);
    m.addEventListener('change', handler);
    return () => m.removeEventListener('change', handler);
  }, [query]);

  return matches;
}
