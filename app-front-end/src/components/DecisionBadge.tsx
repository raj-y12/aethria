import { DECISION_LABELS } from '../design-system/semantics';

export type DecisionBadgeVariant = 'INVEST' | 'PASS' | 'MONITOR' | 'awaiting' | 'undecided' | 'escalation';

/**
 * Compact decision badge — 9px mono, minimal padding, no responsive size inflation.
 * INVEST: solid oxford fill (confirmed invest)
 * MONITOR: bordered, oxford/60 (watch list)
 * PASS: bordered, very muted (rejected)
 * awaiting / undecided: ghost, very muted
 * escalation: accent fill
 */
const VARIANT_CLASS: Record<DecisionBadgeVariant, string> = {
  INVEST:    'bg-oxford text-paper border border-oxford',
  PASS:      'border border-oxford/20 text-oxford/40',
  MONITOR:   'border border-oxford/35 text-oxford/65',
  awaiting:  'border border-hairline text-oxford/25',
  undecided: 'border border-hairline text-oxford/25',
  escalation:'bg-escalation border border-escalation text-white',
};

const LABEL: Record<DecisionBadgeVariant, string> = {
  INVEST:    DECISION_LABELS.INVEST    ?? 'Invest',
  PASS:      DECISION_LABELS.PASS      ?? 'Pass',
  MONITOR:   DECISION_LABELS.MONITOR   ?? 'Monitor',
  awaiting:  'Awaiting',
  undecided: 'Pending',
  escalation:'Escalation',
};

export default function DecisionBadge({ variant }: { variant: DecisionBadgeVariant }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none type-meta tracking-badge uppercase py-phi-1 px-phi-2 ${VARIANT_CLASS[variant]}`}
      aria-label={LABEL[variant]}
    >
      {LABEL[variant]}
    </span>
  );
}
