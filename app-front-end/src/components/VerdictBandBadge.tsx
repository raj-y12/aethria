import type { ReviewerQualityBand } from '../design-system/semantics';

/**
 * Reviewer quality badge.
 * STRONG — solid oxford fill (highest conviction)
 * MEDIUM — outlined box, no fill (present but open)
 * WEAK   — dot + muted text, minimal footprint
 */
export default function VerdictBandBadge({ band }: { band: ReviewerQualityBand }) {
  if (band === 'STRONG') {
    return (
      <span
        className="inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none font-mono text-[9px] tracking-[0.1em] uppercase py-[2px] px-[5px] bg-oxford text-paper"
        aria-label={band}
      >
        {band}
      </span>
    );
  }

  if (band === 'MEDIUM') {
    return (
      <span
        className="inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none font-mono text-[9px] tracking-[0.1em] uppercase py-[2px] px-[5px] border border-oxford/35 text-oxford/60"
        aria-label={band}
      >
        {band}
      </span>
    );
  }

  // WEAK — dot indicator, no box
  return (
    <span
      className="inline-flex shrink-0 items-center gap-[4px] whitespace-nowrap font-mono text-[9px] tracking-[0.12em] uppercase text-oxford/30"
      aria-label={band}
    >
      <span className="w-[4px] h-[4px] shrink-0 bg-oxford/20" aria-hidden />
      {band}
    </span>
  );
}
