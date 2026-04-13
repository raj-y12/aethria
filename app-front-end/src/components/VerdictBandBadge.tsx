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
        className="inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none type-meta tracking-badge uppercase py-phi-1 px-phi-2 bg-oxford text-paper"
        aria-label={band}
      >
        {band}
      </span>
    );
  }

  if (band === 'MEDIUM') {
    return (
      <span
        className="inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none type-meta tracking-badge uppercase py-phi-1 px-phi-2 border border-oxford/40 text-oxford/60"
        aria-label={band}
      >
        {band}
      </span>
    );
  }

  // WEAK — dot indicator, no box
  return (
    <span
      className="inline-flex shrink-0 items-center gap-phi-1 whitespace-nowrap type-meta tracking-label uppercase text-oxford/25"
      aria-label={band}
    >
      <span className="w-[4px] h-[4px] shrink-0 bg-oxford/20" aria-hidden />
      {band}
    </span>
  );
}
