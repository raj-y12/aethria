import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import gsap from 'gsap';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import type { MapHit } from './DottedMarketMap';

const DottedMarketMap = lazy(() => import('./DottedMarketMap'));

/** In-thesis companies plotted on the field (lon, lat). */
const HITS: MapHit[] = [
  { lon: 103.82, lat: 1.35 }, // Singapore
  { lon: 77.59, lat: 12.97 }, // Bangalore
  { lon: -74.01, lat: 40.71 }, // New York
  { lon: 151.21, lat: -33.87 }, // Sydney
  { lon: -79.38, lat: 43.65 }, // Toronto
  { lon: -0.12, lat: 51.5 }, // London
  { lon: -122.42, lat: 37.77 }, // San Francisco
];

const SCANNING = [
  'Orbital Systems · space infra',
  'Lattice Health · clinical AI',
  'Verge Robotics · automation',
  'Quanta Grid · energy',
  'Meridian Bio · longevity',
  'Halcyon Labs · security',
  'Drift Capital · fintech',
];

const SCANNED_TOTAL = 12408;
const IN_THESIS = HITS.length;

/** The market, rendered as a live dotted world map: the whole field scanned, the few that fit lit. */
export default function MarketSection() {
  const reduce = useReducedMotion();
  const [tick, setTick] = useState(0);
  const scannedRef = useRef<HTMLSpanElement | null>(null);
  const rootRef = useRef<HTMLElement | null>(null);

  // cycle the "scanning" ticker
  useEffect(() => {
    if (reduce) return;
    const id = window.setInterval(() => setTick((t) => (t + 1) % SCANNING.length), 2200);
    return () => window.clearInterval(id);
  }, [reduce]);

  // count up the scanned total once, on first view
  useEffect(() => {
    const el = scannedRef.current;
    const root = rootRef.current;
    if (!el || !root) return;
    if (reduce) {
      el.textContent = SCANNED_TOTAL.toLocaleString();
      return;
    }
    const obs = new IntersectionObserver(
      (entries) => {
        if (!entries[0].isIntersecting) return;
        obs.disconnect();
        const counter = { v: 0 };
        gsap.to(counter, {
          v: SCANNED_TOTAL,
          duration: 2.1,
          ease: 'power2.out',
          onUpdate: () => {
            el.textContent = Math.round(counter.v).toLocaleString();
          },
        });
      },
      { threshold: 0.3 },
    );
    obs.observe(root);
    return () => obs.disconnect();
  }, [reduce]);

  return (
    <section
      id="market"
      ref={rootRef}
      className="w-full border-t border-solid border-[var(--section-divider)]"
      style={{ backgroundColor: 'var(--color-paper)' }}
      aria-labelledby="market-heading"
    >
      <div className="page-margin-x py-[clamp(2rem,4.5vh,3rem)]">
        {/* Raw field header — a terminal readout, not a title block. Typography stays
            small so the map (the actual graphic) carries the section, not a headline. */}
        <div className="np-head flex flex-wrap items-baseline justify-between gap-x-8 gap-y-4">
          <p className="np-label">A3 — Markets</p>
          <p className="font-mono text-[12px] leading-[1.6] tracking-[0.04em] text-[var(--text-secondary)] sm:text-right">
            <span ref={scannedRef} className="text-[var(--color-accent)]">
              {SCANNED_TOTAL.toLocaleString()}
            </span>{' '}
            companies scanned ·{' '}
            <span className="text-[var(--color-accent)]">{IN_THESIS}</span> inside your thesis today
          </p>
        </div>

        <h2
          id="market-heading"
          className="editorial-display mt-6 max-w-[24ch] font-normal text-[clamp(2rem,4.6vw,3.4rem)] leading-[1.02] tracking-[-0.02em] text-[var(--color-oxford)]"
        >
          It watches the whole market. You only see what <span className="italic text-[var(--color-accent)]">fits</span>.
        </h2>

        <p className="mt-8 h-[1em] font-mono text-[11px] uppercase tracking-[0.1em] text-[var(--label-muted)]">
          Scanning ·{' '}
          <AnimatePresence mode="wait" initial={false}>
            <motion.span
              key={tick}
              initial={reduce ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={reduce ? undefined : { opacity: 0 }}
              transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
              className="text-[var(--color-accent)]"
            >
              {SCANNING[tick]}
            </motion.span>
          </AnimatePresence>
        </p>

        <Suspense fallback={<div className="mt-10 h-[clamp(320px,52vw,640px)] w-full" aria-hidden />}>
          <DottedMarketMap hits={HITS} className="mt-10 h-[clamp(320px,52vw,640px)] w-full" />
        </Suspense>

        {/* Figure caption — set like a newspaper photo caption */}
        <p className="np-serif mt-5 max-w-[64ch] text-[13.5px] italic leading-[1.6] text-[var(--text-tertiary)]">
          The field at press time — {SCANNED_TOTAL.toLocaleString()} companies scanned across every market the scouts
          reach; {IN_THESIS} currently inside the active thesis, from San Francisco to Singapore.
        </p>

        <div className="mt-5 flex flex-wrap gap-7 border-t border-solid border-[var(--section-divider)] pt-4 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--label-muted)]">
          <span className="inline-flex items-center gap-2">
            <i className="inline-block h-[7px] w-[7px] rounded-full bg-[var(--label-muted)]" /> Scanned
          </span>
          <span className="inline-flex items-center gap-2">
            <i className="inline-block h-[7px] w-[7px] rounded-full bg-[var(--color-accent)]" /> Inside your thesis
          </span>
          <span className="ml-auto">Live field</span>
        </div>
      </div>
    </section>
  );
}
