import { useEffect, useRef, useState, type CSSProperties } from 'react';

/**
 * Subtle activity overlay for the dispatch dot grid.
 *
 * The grid itself is a static CSS background (`.paper-dot-grid`, 28px cells), so
 * there are no real dot nodes to animate. While a lookup is running we layer a
 * random handful of grid-aligned dots on top that pulse lightly. Each dot fades
 * in/out and, on every cycle, hops to a fresh random cell — so the active set
 * keeps drifting instead of blinking in place. The number of dots is chosen at
 * random each time dispatch becomes active.
 */

// Matches .paper-dot-grid: background-size 28px, dot centered in each cell.
const CELL = 28;
const CENTER = 14;
const DOT = 5; // rendered diameter (px)

interface PulseDot {
  id: number;
  col: number;
  row: number;
  /** seconds */
  delay: number;
  duration: number;
  /** peak opacity for this dot */
  peak: number;
}

function randomDot(id: number, cols: number, rows: number): PulseDot {
  return {
    id,
    col: Math.floor(Math.random() * cols),
    row: Math.floor(Math.random() * rows),
    delay: Math.random() * 0.9,
    duration: 1.9 + Math.random() * 1.8,
    peak: 0.16 + Math.random() * 0.22,
  };
}

export default function DispatchDotPulse({ active }: { active: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const gridRef = useRef({ cols: 1, rows: 1 });
  const [dots, setDots] = useState<PulseDot[]>([]);

  useEffect(() => {
    if (!active) {
      setDots([]);
      return;
    }

    const measure = () => {
      const el = ref.current;
      if (!el) return;
      const { width, height } = el.getBoundingClientRect();
      gridRef.current = {
        cols: Math.max(1, Math.floor(width / CELL)),
        rows: Math.max(1, Math.floor(height / CELL)),
      };
    };

    measure();
    const { cols, rows } = gridRef.current;
    // Random number of simultaneously pulsing dots, scaled a little by area.
    const cap = Math.max(6, Math.min(16, Math.round((cols * rows) / 90)));
    const count = 5 + Math.floor(Math.random() * (cap - 4));
    setDots(Array.from({ length: count }, (_, i) => randomDot(i, cols, rows)));

    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [active]);

  // At each animation cycle end the dot is invisible (keyframe 0%/100% = 0),
  // so relocating it here is seamless — no flicker.
  const relocate = (id: number) => {
    const { cols, rows } = gridRef.current;
    setDots((prev) => prev.map((d) => (d.id === id ? randomDot(id, cols, rows) : d)));
  };

  return (
    <div ref={ref} className="pointer-events-none absolute inset-0 z-0 overflow-hidden" aria-hidden>
      {dots.map((d) => (
        <span
          key={d.id}
          className="dot-grid-pulse absolute"
          onAnimationIteration={() => relocate(d.id)}
          style={
            {
              left: CENTER + d.col * CELL - DOT / 2,
              top: CENTER + d.row * CELL - DOT / 2,
              width: DOT,
              height: DOT,
              animationDelay: `${d.delay}s`,
              animationDuration: `${d.duration}s`,
              '--pulse-peak': d.peak,
            } as CSSProperties
          }
        />
      ))}
    </div>
  );
}
