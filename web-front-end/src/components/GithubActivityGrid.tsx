import { useEffect, useState } from 'react';
import { useReducedMotion } from 'framer-motion';
import { CountUp } from '../lib/CountUp';

interface Day {
  date: string;
  count: number;
  level: 0 | 1 | 2 | 3 | 4;
}

const LEVEL_OPACITY = [0.08, 0.3, 0.5, 0.7, 1];
const STAGGER_MS = 3;

/** Live GitHub contribution grid — public API, no key. Cells sweep in one by one; hover for that day's commit count. */
export default function GithubActivityGrid({ username }: { username: string }) {
  const reduce = useReducedMotion();
  const [days, setDays] = useState<Day[] | null>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [swept, setSwept] = useState(false);
  const [hovered, setHovered] = useState<{ day: Day; x: number; y: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`https://github-contributions-api.jogruber.de/v4/${username}?y=last`)
      .then((r) => r.json())
      .then((data: { contributions: Day[]; total?: { lastYear?: number } }) => {
        if (cancelled) return;
        setDays(data.contributions);
        setTotal(data.total?.lastYear ?? null);
      })
      .catch(() => {
        // ponytail: third-party API down — grid just stays empty, rest of page is unaffected
      });
    return () => {
      cancelled = true;
    };
  }, [username]);

  // Sweep-in plays once per mount, a tick after the cells exist so the transition fires.
  useEffect(() => {
    if (!days || reduce) return;
    const t = requestAnimationFrame(() => setSwept(true));
    return () => cancelAnimationFrame(t);
  }, [days, reduce]);

  if (!days) return null;

  const weeks: Day[][] = [];
  for (let i = 0; i < days.length; i += 7) weeks.push(days.slice(i, i + 7));

  return (
    <div>
      {total !== null && (
        // Counted number over its evidence field — the same device the market plate
        // uses for companies scanned. Tabular figures so the count-up does not jitter.
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.75rem', marginBottom: '1.1rem' }}>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 'clamp(1.7rem, 3.4vw, 2.5rem)',
              lineHeight: 1,
              letterSpacing: '-0.02em',
              color: 'var(--ink)',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            <CountUp to={total} active reduce={!!reduce} format={(n) => n.toLocaleString()} />
          </span>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '9px',
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: 'var(--ink-2)',
            }}
          >
            commits · last twelve months
          </span>
        </div>
      )}
      {/* The count above carries this for assistive tech and touch; the grid itself is decorative. */}
      <div aria-hidden style={{ position: 'relative', display: 'flex', gap: '3px', width: '100%' }}>
        {weeks.map((week, i) => (
          <div key={i} style={{ display: 'flex', flex: 1, flexDirection: 'column', gap: '3px' }}>
            {week.map((day, j) => (
              <div
                key={day.date}
                onMouseEnter={(e) => {
                  const r = e.currentTarget.getBoundingClientRect();
                  setHovered({ day, x: r.left + r.width / 2, y: r.top });
                }}
                onMouseLeave={() => setHovered(null)}
                style={{
                  width: '100%',
                  aspectRatio: '1',
                  backgroundColor: 'var(--accent)',
                  opacity: reduce || swept ? LEVEL_OPACITY[day.level] : 0,
                  transform: reduce || swept ? 'scale(1)' : 'scale(0.3)',
                  transition: reduce ? 'none' : 'opacity 0.3s ease, transform 0.3s ease',
                  transitionDelay: reduce ? '0ms' : `${(i * 7 + j) * STAGGER_MS}ms`,
                  cursor: 'default',
                }}
              />
            ))}
          </div>
        ))}
        {hovered && (
          <div
            style={{
              position: 'fixed',
              left: hovered.x,
              top: hovered.y,
              transform: 'translate(-50%, -100%) translateY(-8px)',
              pointerEvents: 'none',
              zIndex: 10,
              background: 'var(--color-oxford)',
              color: '#fff',
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              letterSpacing: '0.02em',
              padding: '0.4rem 0.6rem',
              whiteSpace: 'nowrap',
            }}
          >
            {hovered.day.count} commit{hovered.day.count === 1 ? '' : 's'} on {hovered.day.date}
          </div>
        )}
      </div>
    </div>
  );
}
