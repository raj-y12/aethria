import { DECISION_LABELS } from '../design-system/semantics';
import { DECISION_BADGE_CLASS, VERDICT_CHIP_CLASS } from '../design-system/verdictBadgeTokens';
import type { DecisionBadgeVariant } from '../lib/decisionBadgeVariant';
import type { VerdictBadgeConfig } from '../lib/fundConfiguration';

export type { DecisionBadgeVariant };

/**
 * Compact decision badge — same chip as memo precedent verdicts.
 * Monochrome by rule: INVEST is the system's only filled chip; everything
 * else reads through ink and border weight (see verdictBadgeTokens).
 */
export const DECISION_BADGE_LABEL: Record<DecisionBadgeVariant, string> = {
  INVEST: (DECISION_LABELS.INVEST ?? 'Invest').toUpperCase(),
  PASS: (DECISION_LABELS.PASS ?? 'Pass').toUpperCase(),
  MONITOR: (DECISION_LABELS.MONITOR ?? 'Monitor').toUpperCase(),
  awaiting: 'AWAITING REVIEW',
  undecided: 'PENDING DECISION',
  escalation: 'ESCALATION',
};

export default function DecisionBadge({
  variant,
  badges: _badges,
  label,
  prominent: _prominent = false,
  queue: _queue = false,
}: {
  variant: DecisionBadgeVariant;
  /** @deprecated Colour-coded chips were retired — verdicts are typographic. */
  badges?: VerdictBadgeConfig[];
  /** Optional override for badge copy (e.g. specific escalation driver). */
  label?: string;
  /** @deprecated Size unified — kept for call-site compatibility. */
  prominent?: boolean;
  /** @deprecated Size unified — kept for call-site compatibility. */
  queue?: boolean;
}) {
  const text = label ?? DECISION_BADGE_LABEL[variant];

  return (
    <span className={`${VERDICT_CHIP_CLASS} ${DECISION_BADGE_CLASS[variant]}`} aria-label={text}>
      {text}
    </span>
  );
}
