import type { DecisionBadgeVariant } from '../../lib/decisionBadgeVariant';
import DecisionBadge from '../DecisionBadge';

interface DocketMarginColumnProps {
  variant: DecisionBadgeVariant;
  score: number;
  prominent: boolean;
}

/* Default labels ("AWAITING REVIEW", "PENDING DECISION") overflow the fixed
   96px margin; the docket uses compact synonyms. */
const MARGIN_CHIP_LABEL: Partial<Record<DecisionBadgeVariant, string>> = {
  escalation: 'NEEDS RULING',
  awaiting: 'AWAITING',
  undecided: 'PENDING',
};

/** Fixed left margin column of a docket row: verdict chip over configured score. */
export default function DocketMarginColumn({ variant, score, prominent }: DocketMarginColumnProps) {
  const hasScore = Number.isFinite(score) && score > 0;
  return (
    <div className="flex w-[96px] shrink-0 flex-col items-end gap-1.5 border-r-2 border-oxford/10 pr-3.5 text-right">
      <DecisionBadge variant={variant} label={MARGIN_CHIP_LABEL[variant]} />
      <span
        className={`tabular-nums transition-all duration-150 ${
          prominent ? 'text-[24px] leading-none text-oxford' : 'text-[15px] leading-none text-oxford/45'
        }`}
        aria-hidden={!hasScore}
      >
        {hasScore ? Math.round(score) : '—'}
      </span>
    </div>
  );
}
