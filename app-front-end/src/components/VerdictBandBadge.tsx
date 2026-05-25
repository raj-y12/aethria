import type { CSSProperties } from 'react';
import type { ReviewerQualityBand } from '../design-system/semantics';
import { REVIEWER_BADGE_CLASS } from '../design-system/verdictBadgeTokens';
import { badgeTextColorForBackground, type VerdictBadgeConfig } from '../lib/fundConfiguration';

/**
 * Reviewer quality badge.
 * All bands are full-fill chips for immediate visual separation.
 */
function badgeStyle(band: ReviewerQualityBand, badges?: VerdictBadgeConfig[]): CSSProperties | undefined {
  const backgroundColor = badges?.find((badge) => badge.id === band)?.backgroundColor;
  if (!backgroundColor) return undefined;
  return {
    backgroundColor,
    color: badgeTextColorForBackground(backgroundColor),
  };
}

export default function VerdictBandBadge({ band, badges }: { band: ReviewerQualityBand; badges?: VerdictBadgeConfig[] }) {
  const style = badgeStyle(band, badges);
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none type-meta tracking-badge uppercase py-phi-1 px-phi-2 ${REVIEWER_BADGE_CLASS[band]}`}
      style={style}
      aria-label={band}
    >
      {band}
    </span>
  );
}
