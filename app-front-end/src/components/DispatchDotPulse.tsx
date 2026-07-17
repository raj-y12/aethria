import { useEffect, useRef, useState, type CSSProperties } from 'react';

/**
 * Subtle activity overlay for the dispatch dot grid.
 *
 * The grid itself is a static CSS background (`.paper-dot-grid`, 28px cells), so
 * there are no real dot nodes to animate. While a lookup is running we layer a
 * random handful of grid-aligned dots on top that pulse lightly.
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
  const dimensionsRef = useRef<{ cols: number; rows: number } | null>(null);
  const [dots, setDots] = useState<PulseDot[]>([]);

  useEffect(() => {
    if (!active) {
      dimensionsRef.current = null;
      setDots([]);
      return;
    }

    const buildDots = (cols: number, rows: number) => {
      dimensionsRef.current = { cols, rows };
      const cap = Math.max(6, Math.min(16, Math.round((cols * rows) / 90)));
      const count = 5 + Math.floor(Math.random() * (cap - 4));
      setDots(Array.from({ length: count }, (_, i) => randomDot(i, cols, rows)));
    };

    const measure = () => {
      const el = ref.current;
      if (!el) return;
      const { width, height } = el.getBoundingClientRect();
      const cols = Math.max(1, Math.floor(width / CELL));
      const rows = Math.max(1, Math.floor(height / CELL));
      if (dimensionsRef.current?.cols === cols && dimensionsRef.current?.rows === rows) return;
      buildDots(cols, rows);
    };

    measure();

    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(measure);
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [active]);

  return (
    <div ref={ref} className="pointer-events-none absolute inset-0 z-0 overflow-hidden" aria-hidden>
      {dots.map((d) => (
        <span
          key={d.id}
          className="dot-grid-pulse absolute"
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
