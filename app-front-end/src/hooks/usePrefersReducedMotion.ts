import { useSyncExternalStore } from 'react';

// `window` can exist without `matchMedia` — jsdom omits it unless a test stubs
// it in. The SSR guard alone left every consumer throwing there, which turned
// adding this hook to a shared component into a crash in unrelated suites.
function hasMatchMedia(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function';
}

function subscribe(onChange: () => void): () => void {
  const mq = hasMatchMedia() ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
  if (!mq) return () => {};
  mq.addEventListener('change', onChange);
  return () => mq.removeEventListener('change', onChange);
}

function getSnapshot(): boolean {
  if (!hasMatchMedia()) return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function getServerSnapshot(): boolean {
  return false;
}

/** Respects OS “reduce motion” for Framer / CSS transitions. */
export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
