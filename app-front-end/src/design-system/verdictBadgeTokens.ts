import type { ReviewerQualityBand } from './semantics';
import type { DecisionBadgeVariant } from '../lib/decisionBadgeVariant';

/**
 * Compact verdict chip — shared with memo precedent badges.
 * Memo-calibrated status type, fixed min-width, tight padding.
 * Transparent + bordered by default (marketing parity) — escalation is the
 * one exception that stays filled.
 */
export const VERDICT_CHIP_CLASS =
  'type-status inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none leading-none min-w-[4.25rem] px-2 py-1 border bg-transparent';

/**
 * Centralized badge semantics to keep decision and quality systems aligned.
 * Verdict is read by LABEL TEXT, not fill color — INVEST/PASS/MONITOR (and the
 * neutral pipeline states) all render as the same ink outline chip. Escalation
 * is the one deliberate exception: a genuine human-attention "fire alarm" that
 * stays filled/strong.
 */
export const DECISION_BADGE_CLASS: Record<DecisionBadgeVariant, string> = {
  INVEST: 'border-oxford/40 text-oxford',
  PASS: 'border-oxford/40 text-oxford',
  MONITOR: 'border-oxford/40 text-oxford',
  awaiting: 'border-oxford/25 text-oxford/70',
  undecided: 'border-oxford/25 text-oxford/70',
  escalation: '!bg-escalation !text-white border-escalation', // the one exception — stays filled
};

/**
 * Reviewer quality intentionally follows the same semantic ramp:
 * strong = positive, medium = watch, weak = negative — but, per the same
 * label-not-color rule, all three render identically.
 */
export const REVIEWER_BADGE_CLASS: Record<ReviewerQualityBand, string> = {
  STRONG: 'border-oxford/40 text-oxford',
  MEDIUM: 'border-oxford/40 text-oxford',
  WEAK: 'border-oxford/40 text-oxford',
};

/**
 * Queue attention annotation tags.
 * burgundy = human intervention / unresolved tension — genuine alert, stays filled.
 * gold / positive = caution / conviction interrupt — mono outline, same as decision badges.
 */
export type QueueAnnotationVariant = 'burgundy' | 'gold' | 'positive';

export const QUEUE_ANNOTATION_CLASS: Record<QueueAnnotationVariant, string> = {
  burgundy: '!bg-escalation !text-white border-escalation', // genuine human-attention alert — stays filled
  gold: 'border bg-transparent border-oxford/40 text-oxford',
  positive: 'border bg-transparent border-oxford/40 text-oxford',
};
