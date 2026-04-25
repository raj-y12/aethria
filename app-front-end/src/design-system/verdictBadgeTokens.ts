import type { ReviewerQualityBand } from './semantics';
import type { DecisionBadgeVariant } from '../components/DecisionBadge';

/**
 * Centralized badge semantics to keep decision and quality systems aligned.
 * All badges are flat, full-fill, square chips (no rounding, no shadows).
 */
export const DECISION_BADGE_CLASS: Record<DecisionBadgeVariant, string> = {
  INVEST: 'bg-[#bfe3cc] text-[#17442d]',
  PASS: 'bg-[#eabfb7] text-[#5e2621]',
  MONITOR: 'bg-[#e5d39f] text-[#5f4716]',
  awaiting: 'bg-[#c9d9ea] text-[#253f5a]',
  undecided: 'bg-[#bccfe5] text-[#213a54]',
  escalation: 'bg-escalation text-white',
};

/**
 * Reviewer quality intentionally follows the same semantic ramp:
 * strong = positive, medium = watch, weak = negative.
 */
export const REVIEWER_BADGE_CLASS: Record<ReviewerQualityBand, string> = {
  STRONG: 'bg-[#bfe3cc] text-[#17442d]',
  MEDIUM: 'bg-[#e5d39f] text-[#5f4716]',
  WEAK: 'bg-[#eabfb7] text-[#5e2621]',
};

