import type { CSSProperties } from 'react';
import { DECISION_LABELS } from '../design-system/semantics';
import { DECISION_BADGE_CLASS, VERDICT_CHIP_CLASS } from '../design-system/verdictBadgeTokens';
import type { DecisionBadgeVariant } from '../lib/decisionBadgeVariant';
import type { VerdictBadgeConfig } from '../lib/fundConfiguration';

export type { DecisionBadgeVariant };

/**
 * Compact decision badge — same chip as memo precedent verdicts.
 * INVEST / PASS / MONITOR use semantic fill colors; pipeline states stay neutral.
 */
export const DECISION_BADGE_LABEL: Record<DecisionBadgeVariant, string> = {
  INVEST: (DECISION_LABELS.INVEST ?? 'Invest').toUpperCase(),
  PASS: (DECISION_LABELS.PASS ?? 'Pass').toUpperCase(),
  MONITOR: (DECISION_LABELS.MONITOR ?? 'Monitor').toUpperCase(),
  awaiting: 'AWAITING REVIEW',
  undecided: 'PENDING DECISION',
  escalation: 'ESCALATION',
};

function badgeBackground(
  variant: DecisionBadgeVariant,
  badges?: VerdictBadgeConfig[],
): CSSProperties | undefined {
  if (variant !== 'INVEST' && variant !== 'MONITOR' && variant !== 'PASS') return undefined;
  const backgroundColor = badges?.find((badge) => badge.id === variant)?.backgroundColor;
  if (!backgroundColor) return undefined;
  return { backgroundColor };
}

export default function DecisionBadge({
  variant,
  badges,
  label,
  prominent: _prominent = false,
  queue: _queue = false,
}: {
  variant: DecisionBadgeVariant;
  badges?: VerdictBadgeConfig[];
  /** Optional override for badge copy (e.g. specific escalation driver). */
  label?: string;
  /** @deprecated Size unified — kept for call-site compatibility. */
  prominent?: boolean;
  /** @deprecated Size unified — kept for call-site compatibility. */
  queue?: boolean;
}) {
  const text = label ?? DECISION_BADGE_LABEL[variant];
  const style = badgeBackground(variant, badges);

  return (
    <span
      className={`${VERDICT_CHIP_CLASS} ${DECISION_BADGE_CLASS[variant]}`}
      style={style}
      aria-label={text}
    >
      {text}
    </span>
  );
}
