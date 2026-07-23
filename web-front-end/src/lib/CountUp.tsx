import { useEffect, useState } from 'react';

/** Counts a single number up on first view; settles instantly under reduced motion. */
export function CountUp({ to, active, reduce }: { to: number; active: boolean; reduce: boolean }) {
  const [n, setN] = useState(reduce ? to : 0);
  useEffect(() => {
    if (reduce || !active) return;
    let raf = 0;
    const start = performance.now();
    const dur = 850;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / dur);
      setN(Math.round(to * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [active, to, reduce]);
  return <>{n}</>;
}
