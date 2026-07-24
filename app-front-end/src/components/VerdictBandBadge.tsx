import type { CSSProperties } from 'react';
import type { ReviewerQualityBand } from '../design-system/semantics';
import { REVIEWER_BADGE_CLASS, VERDICT_CHIP_CLASS } from '../design-system/verdictBadgeTokens';
import type { VerdictBadgeConfig } from '../lib/fundConfiguration';

/**
 * Reviewer quality badge — same chip dimensions as decision / precedent verdicts.
 */
function badgeBackground(band: ReviewerQualityBand, badges?: VerdictBadgeConfig[]): CSSProperties | undefined {
  const backgroundColor = badges?.find((badge) => badge.id === band)?.backgroundColor;
  if (!backgroundColor) return undefined;
  return { backgroundColor };
}

export default function VerdictBandBadge({ band, badges }: { band: ReviewerQualityBand; badges?: VerdictBadgeConfig[] }) {
  const style = badgeBackground(band, badges);
  return (
    <span
      className={`${VERDICT_CHIP_CLASS} ${REVIEWER_BADGE_CLASS[band]}`}
      style={style}
      aria-label={band}
    >
      {band}
    </span>
  );
}
