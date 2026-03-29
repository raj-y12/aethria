import { DECISION_LABELS } from '../design-system/semantics';

export type DecisionBadgeVariant = 'YES' | 'NO' | 'MAYBE' | 'awaiting' | 'undecided' | 'escalation';

const VARIANT_CLASS: Record<DecisionBadgeVariant, string> = {
  YES:
    'bg-transparent border border-solid border-oxford/20 py-1 px-2 font-mono uppercase text-[10px] leading-[1.5] tracking-[0.1em] text-oxford/85 shadow-none',
  NO:
    'bg-transparent border border-solid border-oxford/15 py-1 px-2 font-mono uppercase text-[10px] leading-[1.5] tracking-[0.1em] text-oxford/55 shadow-none',
  MAYBE:
    'bg-transparent border border-solid border-oxford/18 py-1 px-2 font-mono uppercase text-[10px] leading-[1.5] tracking-[0.1em] text-oxford/70 shadow-none',
  awaiting:
    'bg-transparent border-0 py-0 px-0 font-mono uppercase text-[9px] leading-[1.5] tracking-[0.08em] text-oxford/35 shadow-none',
  undecided:
    'bg-transparent border-0 py-0 px-0 font-mono uppercase text-[9px] leading-[1.5] tracking-[0.08em] text-oxford/45 shadow-none',
  escalation:
    'border-0 bg-[#7D2B3A] py-1 px-2 font-mono uppercase text-[10px] leading-[1.5] tracking-[0.1em] text-white shadow-none',
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
      className={`inline-flex items-center justify-center rounded-none ${VARIANT_CLASS[variant]}`}
      aria-label={LABEL_OVERRIDE[variant]}
    >
      {LABEL_OVERRIDE[variant]}
    </span>
  );
}
