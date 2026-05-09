import type { ReviewerQualityBand } from '../design-system/semantics';
import { REVIEWER_BADGE_CLASS } from '../design-system/verdictBadgeTokens';

/**
 * Reviewer quality badge.
 * All bands are full-fill chips for immediate visual separation.
 */
export default function VerdictBandBadge({ band }: { band: ReviewerQualityBand }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none type-meta tracking-badge uppercase py-phi-1 px-phi-2 ${REVIEWER_BADGE_CLASS[band]}`}
      aria-label={band}
    >
      {band}
    </span>
  );
}
