import type { HumanRulingDecision } from '../api/decisions';
import type { RecommendationState } from '../api/evaluations';
import type { Partner } from '../types/startup';
import { DECISION_LABELS } from '../design-system/semantics';

export function partnerRecommendationLabel(partner?: Partner | null): string | null {
  if (!partner) return null;
  if (partner.operational_action) {
    return { ADVANCE: 'Advance', PASS: 'Pass', MONITOR: 'Monitor', MORE_DILIGENCE: 'More diligence' }[partner.operational_action];
  }
  const canonical = partner.provenance?.canonical_recommendation;
  if (['PARTNER_ANALYSIS', 'PARTNER_CANONICAL_MAPPING'].includes(partner.provenance?.recommendation_origin ?? '') && canonical) {
    if (canonical === 'insufficient_evidence') return 'More diligence';
    if (canonical === 'advance') return 'Advance';
    if (canonical === 'pass') return 'Pass';
    if (canonical === 'monitor') return 'Monitor';
  }
  return DECISION_LABELS[partner.recommendation] ?? partner.recommendation;
}

type RecommendationSemantics = {
  label: string;
  explanation: string;
  defaultRuling: HumanRulingDecision | null;
  alignedRulings: readonly HumanRulingDecision[];
};

const RECOMMENDATION_SEMANTICS: Readonly<
  Record<RecommendationState, RecommendationSemantics>
> = {
  advance: {
    label: 'Advance',
    explanation: 'Aethria sees enough grounded evidence to advance the opportunity.',
    defaultRuling: 'advance',
    alignedRulings: ['advance'],
  },
  monitor: {
    label: 'Monitor',
    explanation: 'Aethria sees a case worth watching, but not enough support to advance today.',
    defaultRuling: 'monitor',
    alignedRulings: ['monitor'],
  },
  pass: {
    label: 'Pass',
    explanation: 'Aethria sees enough grounded evidence to recommend passing on the opportunity.',
    defaultRuling: 'pass',
    alignedRulings: ['pass'],
  },
  insufficient_evidence: {
    label: 'Insufficient evidence',
    explanation: 'Aethria does not yet have enough grounded evidence to make a decisive recommendation.',
    defaultRuling: null,
    alignedRulings: [],
  },
};

export function recommendationSemantics(
  recommendation: RecommendationState,
): RecommendationSemantics {
  return RECOMMENDATION_SEMANTICS[recommendation];
}

export function defaultRulingForRecommendation(
  recommendation?: RecommendationState | null,
): HumanRulingDecision | null {
  return recommendation
    ? RECOMMENDATION_SEMANTICS[recommendation].defaultRuling
    : null;
}

export function rulingAlignsWithRecommendation(
  recommendation?: RecommendationState | null,
  ruling?: HumanRulingDecision | null,
): boolean {
  if (!recommendation) return true;
  if (!ruling) return false;
  return RECOMMENDATION_SEMANTICS[recommendation].alignedRulings.includes(ruling);
}
