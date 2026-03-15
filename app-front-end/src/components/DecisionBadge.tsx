import { DECISION_LABELS } from '../design-system/semantics';

export type DecisionBadgeVariant = 'YES' | 'NO' | 'MAYBE' | 'awaiting';

const VARIANT_CLASS: Record<DecisionBadgeVariant, string> = {
  YES: 'bg-oxford text-ivory',
  NO: 'bg-oxford/10 text-oxford border border-oxford/25',
  MAYBE: 'bg-oxford/15 text-oxford border border-oxford/25',
  awaiting: 'bg-oxford text-ivory',
};

const LABEL_OVERRIDE: Record<DecisionBadgeVariant, string> = {
  YES: DECISION_LABELS.YES ?? 'Advance',
  NO: DECISION_LABELS.NO ?? 'Pass',
  MAYBE: DECISION_LABELS.MAYBE ?? 'Hold',
  awaiting: 'Awaiting review',
};

/**
 * Canonical decision badge: one shape, size, typography. Used in WorkGrid, memo, feed.
 * Colours from brand palette only (oxford, ivory, oxford opacity ladder).
 */
export default function DecisionBadge({ variant }: { variant: DecisionBadgeVariant }) {
  return (
    <span
      className={`inline-flex items-center justify-center py-2 px-3 type-label-tab rounded-none ${VARIANT_CLASS[variant]}`}
      aria-label={LABEL_OVERRIDE[variant]}
    >
      {LABEL_OVERRIDE[variant]}
    </span>
  );
}
