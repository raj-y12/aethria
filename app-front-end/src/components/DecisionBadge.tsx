import { DECISION_LABELS } from '../design-system/semantics';
import { DECISION_BADGE_CLASS } from '../design-system/verdictBadgeTokens';
import type { DecisionBadgeVariant } from '../lib/decisionBadgeVariant';

export type { DecisionBadgeVariant };

/**
 * Compact decision badge — 9px mono, minimal padding, no responsive size inflation.
 * INVEST / PASS / MONITOR are all full-fill semantic chips for instant scanability.
 * awaiting / undecided remain neutral full-fill chips.
 * escalation remains accent fill.
 */
export const DECISION_BADGE_LABEL: Record<DecisionBadgeVariant, string> = {
  INVEST: (DECISION_LABELS.INVEST ?? 'Invest').toUpperCase(),
  PASS: (DECISION_LABELS.PASS ?? 'Pass').toUpperCase(),
  MONITOR: (DECISION_LABELS.MONITOR ?? 'Monitor').toUpperCase(),
  awaiting: 'AWAITING REVIEW',
  undecided: 'PENDING DECISION',
  escalation: 'ESCALATION',
};

export default function DecisionBadge({ variant }: { variant: DecisionBadgeVariant }) {
  const text = DECISION_BADGE_LABEL[variant];
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none type-meta tracking-badge uppercase py-phi-1 px-phi-2 ${DECISION_BADGE_CLASS[variant]}`}
      aria-label={text}
    >
      {text}
    </span>
  );
}
