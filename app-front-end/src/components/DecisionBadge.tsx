import type { CSSProperties } from 'react';
import { DECISION_LABELS } from '../design-system/semantics';
import { DECISION_BADGE_CLASS } from '../design-system/verdictBadgeTokens';
import type { DecisionBadgeVariant } from '../lib/decisionBadgeVariant';
import { badgeTextColorForBackground, type VerdictBadgeConfig } from '../lib/fundConfiguration';

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

function badgeStyle(variant: DecisionBadgeVariant, badges?: VerdictBadgeConfig[]): CSSProperties | undefined {
  if (variant !== 'INVEST' && variant !== 'MONITOR' && variant !== 'PASS') return undefined;
  const backgroundColor = badges?.find((badge) => badge.id === variant)?.backgroundColor;
  if (!backgroundColor) return undefined;
  return {
    backgroundColor,
    color: badgeTextColorForBackground(backgroundColor),
  };
}

export default function DecisionBadge({
  variant,
  badges,
  label,
  prominent = false,
  queue = false,
}: {
  variant: DecisionBadgeVariant;
  badges?: VerdictBadgeConfig[];
  /** Optional override for badge copy (e.g. specific escalation driver). */
  label?: string;
  /** Larger chip for queue scan hierarchy. */
  prominent?: boolean;
  /** Queue docket — filled colour, slightly tighter than default chips. */
  queue?: boolean;
}) {
  const text = label ?? DECISION_BADGE_LABEL[variant];
  const style = badgeStyle(variant, badges);
  const sizeClass = queue
    ? prominent
      ? 'font-mono text-[10px] tracking-[0.12em] py-[3px] px-phi-2'
      : 'font-mono text-[9px] tracking-[0.11em] py-[2px] px-phi-2'
    : prominent
      ? 'font-mono text-[11px] tracking-[0.1em] py-[5px] px-phi-3'
      : 'type-meta py-phi-1 px-phi-2';

  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none font-medium tracking-badge uppercase ${sizeClass} ${DECISION_BADGE_CLASS[variant]}`}
      style={style}
      aria-label={text}
    >
      {text}
    </span>
  );
}
