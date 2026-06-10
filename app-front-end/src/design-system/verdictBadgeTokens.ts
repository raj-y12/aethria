import type { ReviewerQualityBand } from './semantics';
import type { DecisionBadgeVariant } from '../lib/decisionBadgeVariant';

/**
 * Compact verdict chip — shared with memo precedent badges.
 * 9px mono, semibold, fixed min-width, tight padding.
 */
export const VERDICT_CHIP_CLASS =
  'inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none font-mono font-semibold uppercase leading-none min-w-[4.25rem] px-2 py-1 text-[9px] tracking-[0.1em]';

/**
 * Verdicts are typographic, not colour-coded — the word carries the call
 * (the same rule the memo cover established). One fill in the whole system:
 * INVEST, in oxford, because conviction earns the only strong mark. Everything
 * else is ink and border weight. Burgundy stays reserved for human attention.
 */
export const DECISION_BADGE_CLASS: Record<DecisionBadgeVariant, string> = {
  INVEST: 'bg-oxford text-paper',
  MONITOR: 'border border-oxford/35 bg-transparent text-oxford/75',
  PASS: 'border border-oxford/[0.14] bg-transparent text-oxford/48',
  awaiting: 'border border-oxford/[0.12] bg-transparent text-oxford/40',
  undecided: 'border border-oxford/[0.12] bg-transparent text-oxford/40',
  escalation: 'border border-escalation/45 bg-transparent text-escalation',
};

/**
 * Reviewer quality follows the same monochrome ramp: strength reads as ink
 * weight, not hue.
 */
export const REVIEWER_BADGE_CLASS: Record<ReviewerQualityBand, string> = {
  STRONG: 'border border-oxford/45 bg-transparent text-oxford/85',
  MEDIUM: 'border border-oxford/[0.18] bg-transparent text-oxford/55',
  WEAK: 'border border-oxford/[0.10] bg-transparent text-oxford/38',
};

/**
 * Queue attention annotations — plain text marks, no fills. They annotate;
 * the verdict is the row's only chip.
 * burgundy = human intervention / unresolved tension (escalation ink)
 * gold = caution / incomplete confidence (muted ink — no decorative gold)
 * positive = strong conviction interrupt
 */
export type QueueAnnotationVariant = 'burgundy' | 'gold' | 'positive';

export const QUEUE_ANNOTATION_CLASS: Record<QueueAnnotationVariant, string> = {
  burgundy: 'text-escalation/85',
  gold: 'text-oxford/55',
  positive: 'text-oxford/70',
};
