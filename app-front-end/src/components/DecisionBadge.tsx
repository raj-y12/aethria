import { DECISION_LABELS } from '../design-system/semantics';

export type DecisionBadgeVariant = 'YES' | 'NO' | 'MAYBE' | 'awaiting' | 'undecided' | 'escalation';

const VARIANT_CLASS: Record<DecisionBadgeVariant, string> = {
  YES:
    'type-label-tab border border-solid border-oxford/20 bg-transparent py-1 px-2 uppercase text-oxford/85 shadow-none',
  NO:
    'type-label-tab border border-solid border-oxford/15 bg-transparent py-1 px-2 uppercase text-oxford/55 shadow-none',
  MAYBE:
    'type-label-tab border border-solid border-oxford/18 bg-transparent py-1 px-2 uppercase text-oxford/70 shadow-none',
  awaiting:
    'type-meta border-0 bg-transparent px-0 py-0 text-[9px] uppercase tracking-[0.1em] text-oxford/35 shadow-none',
  undecided:
    'type-meta border-0 bg-transparent px-0 py-0 text-[9px] uppercase tracking-[0.1em] text-oxford/45 shadow-none',
  escalation:
    'type-label-tab border-0 bg-[#7D2B3A] py-1 px-2 uppercase text-white shadow-none',
};

const LABEL_OVERRIDE: Record<DecisionBadgeVariant, string> = {
  YES: DECISION_LABELS.YES ?? 'Advance',
  NO: DECISION_LABELS.NO ?? 'Pass',
  MAYBE: DECISION_LABELS.MAYBE ?? 'Hold',
  awaiting: 'Awaiting review',
  undecided: 'Awaiting decision',
  escalation: 'Human review',
};

/**
 * Canonical decision badge: one shape, size, typography. Used in WorkGrid, memo, feed.
 * Colours from brand palette only (oxford, white on escalation badge, oxford opacity ladder).
 */
export default function DecisionBadge({ variant }: { variant: DecisionBadgeVariant }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none ${VARIANT_CLASS[variant]}`}
      aria-label={LABEL_OVERRIDE[variant]}
    >
      {LABEL_OVERRIDE[variant]}
    </span>
  );
}
