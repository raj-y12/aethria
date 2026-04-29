import type { ReviewerQualityBand } from '../design-system/semantics';
import { REVIEWER_BADGE_CLASS } from '../design-system/verdictBadgeTokens';

/**
 * Reviewer quality badge.
 * All bands are full-fill chips for immediate visual separation.
 */
export default function VerdictBandBadge({ band }: { band: ReviewerQualityBand }) {
  const label = band.charAt(0) + band.slice(1).toLowerCase();
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none type-meta tracking-badge py-phi-1 px-phi-2 ${REVIEWER_BADGE_CLASS[band]}`}
      aria-label={label}
    >
      {label}
    </span>
  );
}
