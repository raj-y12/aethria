import type { Startup } from '../types/startup';

export type DecisionBadgeVariant =
  | 'INVEST'
  | 'PASS'
  | 'MONITOR'
  | 'awaiting'
  | 'undecided'
  | 'escalation';

/** Same pipeline semantics as WorkGrid row badges — escalation before recommendation. */
export function getDecisionBadgeVariant(s: Startup): DecisionBadgeVariant {
  if (s.human_resolution?.decision === 'YES') return 'INVEST';
  if (s.human_resolution?.decision === 'NO') return 'PASS';
  if (s.human_resolution?.decision === 'MAYBE') return 'MONITOR';
  if (s.partner != null && s.partner.human_review_required === true) return 'escalation';
  const rec = s.partner?.recommendation;
  if (!rec) return s.review ? 'undecided' : 'awaiting';
  if (rec === 'INVEST') return 'INVEST';
  if (rec === 'PASS') return 'PASS';
  return 'MONITOR';
}
