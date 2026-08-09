import { useEffect, useRef, useState } from 'react';

/**
 * Fires once when the ref'd element enters the viewport, then disconnects.
 * When `reduce` is true (prefers-reduced-motion) or IntersectionObserver is
 * unavailable, resolves to `true` immediately without observing.
 */
export function useInView<T extends Element>(reduce: boolean | null, threshold = 0.3) {
  const ref = useRef<T | null>(null);
  const [isIn, setIsIn] = useState(false);

  useEffect(() => {
    if (reduce || typeof IntersectionObserver === 'undefined') {
      setIsIn(true);
      return;
    }
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        obs.disconnect();
        setIsIn(true);
      },
      { threshold },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [reduce, threshold]);

  return [ref, isIn] as const;
}
