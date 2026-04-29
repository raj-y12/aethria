import { DECISION_LABELS } from '../design-system/semantics';
import { DECISION_BADGE_CLASS } from '../design-system/verdictBadgeTokens';

export type DecisionBadgeVariant = 'INVEST' | 'PASS' | 'MONITOR' | 'awaiting' | 'undecided' | 'escalation';

/**
 * Compact decision badge — 9px mono, minimal padding, no responsive size inflation.
 * INVEST / PASS / MONITOR are all full-fill semantic chips for instant scanability.
 * awaiting / undecided remain neutral full-fill chips.
 * escalation remains accent fill.
 */
const LABEL: Record<DecisionBadgeVariant, string> = {
  INVEST: DECISION_LABELS.INVEST ?? 'Invest',
  PASS: DECISION_LABELS.PASS ?? 'Pass',
  MONITOR: DECISION_LABELS.MONITOR ?? 'Monitor',
  awaiting: 'Awaiting Review',
  undecided: 'Pending Decision',
  escalation: 'Escalation',
};

export default function DecisionBadge({ variant }: { variant: DecisionBadgeVariant }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none type-meta tracking-badge py-phi-1 px-phi-2 ${DECISION_BADGE_CLASS[variant]}`}
      aria-label={LABEL[variant]}
    >
      {LABEL[variant]}
    </span>
  );
}
