import type { ReviewerQualityBand } from './semantics';
import type { DecisionBadgeVariant } from '../lib/decisionBadgeVariant';

/**
 * Compact verdict chip — shared with memo precedent badges.
 * Memo-calibrated status type, fixed min-width, tight padding.
 * Filled by default (cooled, muted tones — not the old loud pastels);
 * escalation is the one exception at full strength.
 */
export const VERDICT_CHIP_CLASS =
  'type-status inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none leading-none min-w-[4.25rem] px-2 py-1';

/**
 * Centralized badge semantics to keep decision and quality systems aligned.
 * Cooled, muted fills — one quiet family, not a loud traffic-light ramp.
 * Escalation is the one deliberate exception: a genuine human-attention
 * "fire alarm" that stays filled/strong at full saturation.
 */
export const DECISION_BADGE_CLASS: Record<DecisionBadgeVariant, string> = {
  INVEST: 'bg-[#c3d3c9] text-oxford',
  PASS: 'bg-[#d6c4c0] text-oxford',
  MONITOR: 'bg-[#cfccbb] text-oxford',
  awaiting: 'bg-oxford/[0.06] text-oxford/70',
  undecided: 'bg-oxford/[0.06] text-oxford/70',
  escalation: 'bg-escalation !text-white', // the one exception — stays filled, full strength
};

/**
 * Reviewer quality follows the same cooled semantic ramp as decision badges.
 */
export const REVIEWER_BADGE_CLASS: Record<ReviewerQualityBand, string> = {
  STRONG: 'bg-[#c3d3c9] text-oxford',
  MEDIUM: 'bg-[#cfccbb] text-oxford',
  WEAK: 'bg-[#d6c4c0] text-oxford',
};

/**
 * Queue attention annotation tags.
 * burgundy = human intervention / unresolved tension — genuine alert, stays filled/strong.
 * gold / positive = caution / conviction interrupt — cooled fill, same family as decision badges.
 */
export type QueueAnnotationVariant = 'burgundy' | 'gold' | 'positive';

export const QUEUE_ANNOTATION_CLASS: Record<QueueAnnotationVariant, string> = {
  burgundy: 'bg-escalation !text-white', // genuine human-attention alert — stays filled
  gold: 'bg-[#cfccbb] text-oxford',
  positive: 'bg-[#c3d3c9] text-oxford',
};
