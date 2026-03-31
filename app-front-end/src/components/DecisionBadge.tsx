import { DECISION_LABELS } from '../design-system/semantics';

export type DecisionBadgeVariant = 'YES' | 'NO' | 'MAYBE' | 'awaiting' | 'undecided' | 'escalation';

const BADGE_BASE_CLASS =
  'type-label-tab py-1 px-2 uppercase shadow-none';

const VARIANT_CLASS: Record<DecisionBadgeVariant, string> = {
  YES:
    `${BADGE_BASE_CLASS} bg-oxford text-paper`,
  NO:
    `${BADGE_BASE_CLASS} border border-solid border-oxford/15 bg-transparent text-oxford/55`,
  MAYBE:
    `${BADGE_BASE_CLASS} bg-oxford/10 text-oxford/80`,
  awaiting:
    `${BADGE_BASE_CLASS} border border-solid border-oxford/10 bg-transparent text-oxford/35`,
  undecided:
    `${BADGE_BASE_CLASS} border border-solid border-oxford/12 bg-transparent text-oxford/45`,
  escalation:
    `${BADGE_BASE_CLASS} bg-escalation text-white`,
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
