import type { DecisionBadgeVariant } from '../../lib/decisionBadgeVariant';
import DecisionBadge from '../DecisionBadge';

interface DocketMarginColumnProps {
  variant: DecisionBadgeVariant;
  score: number;
  prominent: boolean;
}

/** Fixed left margin column of a docket row: verdict chip over configured score. */
export default function DocketMarginColumn({ variant, score, prominent }: DocketMarginColumnProps) {
  const hasScore = Number.isFinite(score) && score > 0;
  return (
    <div className="flex w-[96px] shrink-0 flex-col items-end gap-1.5 border-r-2 border-oxford/10 pr-3.5 text-right">
      <DecisionBadge variant={variant} label={variant === 'escalation' ? 'NEEDS RULING' : undefined} />
      <span
        className={`tabular-nums transition-all duration-150 ${
          prominent ? 'text-[24px] leading-none text-oxford' : 'text-[15px] leading-none text-oxford/45'
        }`}
        aria-hidden={!hasScore}
      >
        {hasScore ? score.toFixed(1) : '—'}
      </span>
    </div>
  );
}
