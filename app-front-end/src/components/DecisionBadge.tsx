import { DECISION_LABELS } from '../design-system/semantics';

export type DecisionBadgeVariant = 'YES' | 'NO' | 'MAYBE' | 'awaiting' | 'undecided' | 'escalation';

/**
 * Compact decision badge — 9px mono, minimal padding, no responsive size inflation.
 * YES: solid oxford fill (confirmed advance)
 * NO / MAYBE: bordered, no fill
 * awaiting / undecided: ghost, very muted
 * escalation: accent fill
 */
const VARIANT_CLASS: Record<DecisionBadgeVariant, string> = {
  YES:       'bg-oxford text-paper border border-oxford',
  NO:        'border border-oxford/20 text-oxford/40',
  MAYBE:     'border border-oxford/30 text-oxford/55',
  awaiting:  'border border-oxford/[0.12] text-oxford/25',
  undecided: 'border border-oxford/[0.12] text-oxford/30',
  escalation:'bg-escalation border border-escalation text-white',
};

const LABEL: Record<DecisionBadgeVariant, string> = {
  YES:       DECISION_LABELS.YES ?? 'Advance',
  NO:        DECISION_LABELS.NO  ?? 'Pass',
  MAYBE:     DECISION_LABELS.MAYBE ?? 'Hold',
  awaiting:  'Awaiting',
  undecided: 'Pending',
  escalation:'Escalation',
};

export default function DecisionBadge({ variant }: { variant: DecisionBadgeVariant }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none font-mono text-[9px] tracking-[0.1em] uppercase py-[2px] px-[5px] ${VARIANT_CLASS[variant]}`}
      aria-label={LABEL[variant]}
    >
      {LABEL[variant]}
    </span>
  );
}
