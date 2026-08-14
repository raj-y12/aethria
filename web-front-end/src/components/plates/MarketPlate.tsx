import { useEffect, useRef } from 'react';
import gsap from 'gsap';
import { useReducedMotion } from 'framer-motion';
import DottedMarketMap, { type MapHit } from '../DottedMarketMap';
import Plate from '../Plate';
import { useInView } from '../../lib/useInView';

/** In-thesis companies plotted on the field (lon, lat). Copied verbatim from MarketSection. */
const HITS: MapHit[] = [
  { lon: 103.82, lat: 1.35 }, // Singapore
  { lon: 77.59, lat: 12.97 }, // Bangalore
  { lon: -74.01, lat: 40.71 }, // New York
  { lon: 151.21, lat: -33.87 }, // Sydney
  { lon: -79.38, lat: 43.65 }, // Toronto
  { lon: -0.12, lat: 51.5 }, // London
  { lon: -122.42, lat: 37.77 }, // San Francisco
];

const SCANNED_TOTAL = 12408;
const IN_THESIS = HITS.length;

/** Plate 01 — the market, rendered as the live dotted world map centerpiece. */
export default function MarketPlate() {
  const reduce = useReducedMotion();
  const scannedRef = useRef<HTMLSpanElement | null>(null);
  const [rootRef, isIn] = useInView<HTMLDivElement>(reduce, 0.3);

  // count up the scanned total once, on first view
  useEffect(() => {
    const el = scannedRef.current;
    if (!el) return;
    if (reduce) {
      el.textContent = SCANNED_TOTAL.toLocaleString();
      return;
    }
    if (!isIn) return;
    const counter = { v: 0 };
    gsap.to(counter, {
      v: SCANNED_TOTAL,
      duration: 2.1,
      ease: 'power2.out',
      onUpdate: () => {
        el.textContent = Math.round(counter.v).toLocaleString();
      },
    });
  }, [reduce, isIn]);

  return (
    <Plate
      id="market"
      index="01 — 08"
      title="The Market"
      capLeft="Market intelligence / live field"
      capRight="Every company scanned · the few that fit"
      tone="image-led"
    >
      <div ref={rootRef}>
        <div className="market-stage reveal d2">
          <DottedMarketMap hits={HITS} className="h-full w-full" />
        </div>

        <p className="caption reveal d3">
          Every company reads as a faint mark. The few inside your active thesis glow; scouts fire toward them and
          conviction spreads through the surrounding field. The field at press time —{' '}
          <span ref={scannedRef} className="text-[var(--accent)]">
            {SCANNED_TOTAL.toLocaleString()}
          </span>{' '}
          companies scanned · <span className="text-[var(--accent)]">{IN_THESIS}</span> inside your thesis today.
        </p>

        <div className="reveal d3 mt-5 flex flex-wrap gap-7 border-t border-solid border-[var(--line)] pt-4 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--ink-2)]">
          <span className="inline-flex items-center gap-2">
            <i className="inline-block h-[7px] w-[7px] rounded-full bg-[var(--ink-3)]" /> Scanned
          </span>
          <span className="inline-flex items-center gap-2">
            <i className="inline-block h-[7px] w-[7px] rounded-full bg-[var(--accent)]" /> Inside your thesis
          </span>
        </div>
      </div>
    </Plate>
  );
}
