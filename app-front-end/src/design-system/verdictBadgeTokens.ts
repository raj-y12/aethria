import type { ReviewerQualityBand } from './semantics';
import type { DecisionBadgeVariant } from '../lib/decisionBadgeVariant';

/**
 * Compact verdict chip — shared with memo precedent badges.
 * Memo-calibrated status type, fixed min-width, tight padding.
 */
export const VERDICT_CHIP_CLASS =
  'type-status inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none leading-none min-w-[4.25rem] px-2 py-1';

/**
 * Centralized badge semantics to keep decision and quality systems aligned.
 * All badges are flat, full-fill, square chips (no rounding, no shadows).
 */
export const DECISION_BADGE_CLASS: Record<DecisionBadgeVariant, string> = {
  INVEST: 'bg-[#bfe3cc] !text-[#17442d]',
  PASS: 'bg-[#eabfb7] !text-[#5e2621]',
  MONITOR: 'bg-[#e5d39f] !text-[#5f4716]',
  awaiting: 'bg-[#c9d9ea] !text-[#253f5a]',
  undecided: 'bg-[#bccfe5] !text-[#213a54]',
  escalation: 'bg-escalation !text-white',
};

/**
 * Reviewer quality intentionally follows the same semantic ramp:
 * strong = positive, medium = watch, weak = negative.
 */
export const REVIEWER_BADGE_CLASS: Record<ReviewerQualityBand, string> = {
  STRONG: 'bg-[#bfe3cc] !text-[#17442d]',
  MEDIUM: 'bg-[#e5d39f] !text-[#5f4716]',
  WEAK: 'bg-[#eabfb7] !text-[#5e2621]',
};

/**
 * Queue attention annotation tags — restrained filled markers (not outline chips).
 * burgundy = human intervention / unresolved tension
 * gold = caution / incomplete confidence
 * positive = strong conviction interrupt (quieter than burgundy)
 */
export type QueueAnnotationVariant = 'burgundy' | 'gold' | 'positive';

export const QUEUE_ANNOTATION_CLASS: Record<QueueAnnotationVariant, string> = {
  burgundy: 'bg-[#7D2B3A] !text-[#F4F1EA]',
  gold: 'bg-[#d9c9a3] !text-[#4a3810]',
  positive: 'bg-[#b5d4bc] !text-[#17442d]',
};
