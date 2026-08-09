import type { FundHypothesis, FundObservation } from '../api/fundIntelligence';

const SUFFICIENCY_RANK: Record<string, number> = {
  insufficient: 0,
  emerging: 1,
  moderate: 2,
  strong: 3,
};

const FAMILY_PRIORITY: Record<string, number> = {
  criterion_tradeoff: 5,
  practical_gate: 4,
  discounted_risk: 3,
  override_rate: 2,
  mandate_behavior: 2,
  recurring_factor: 1,
};

function rank(value: string): number {
  return SUFFICIENCY_RANK[value] ?? 0;
}

export function selectLeadObservation(observations: FundObservation[]): FundObservation | null {
  return [...observations].sort((left, right) => (
    rank(right.sufficiency) - rank(left.sufficiency)
    || right.sample_size - left.sample_size
    || (FAMILY_PRIORITY[right.observation_type] ?? 0) - (FAMILY_PRIORITY[left.observation_type] ?? 0)
    || right.supporting_case_ids.length - left.supporting_case_ids.length
    || left.observation_id.localeCompare(right.observation_id)
  ))[0] ?? null;
}

export function selectLeadHypothesis(hypotheses: FundHypothesis[]): FundHypothesis | null {
  return [...hypotheses].sort((left, right) => (
    rank(right.sufficiency) - rank(left.sufficiency)
    || right.sample_size - left.sample_size
    || right.supporting_case_ids.length - left.supporting_case_ids.length
    || left.hypothesis_id.localeCompare(right.hypothesis_id)
  ))[0] ?? null;
}

export function formatObservationFamily(family: string): string {
  const labels: Record<string, string> = {
    criterion_tradeoff: 'Criterion trade-off',
    practical_gate: 'Practical gate',
    discounted_risk: 'Discounted risk',
    override_rate: 'Override behavior',
    mandate_behavior: 'Mandate behavior',
    recurring_factor: 'Recurring factor',
    recommendation_ruling_agreement: 'Decision alignment',
  };
  return labels[family] ?? family.replace(/_/g, ' ').replace(/^./, (value) => value.toUpperCase());
}

function titleCase(value: string): string {
  return value.replace(/[_-]/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase());
}

export function formatObservationSegment(segment: Record<string, string>): string {
  if (segment.scope === 'fund') return 'Across the fund';
  if (segment.dimension && segment.value) return `${titleCase(segment.value)} · ${titleCase(segment.dimension)}`;
  if (segment.factor) return titleCase(segment.factor);
  return 'Historical decision set';
}

export function observationStatement(observation: FundObservation): string {
  const direction = observation.direction ?? '';
  if (observation.observation_type === 'criterion_tradeoff') {
    const strong = direction.match(/strong ([^/]+)/)?.[1]?.trim();
    const weak = direction.match(/weak (.+)$/)?.[1]?.trim();
    if (strong && weak) return `The fund appears to tolerate weak ${titleCase(weak)} when ${titleCase(strong)} is strong.`;
  }
  if (observation.observation_type === 'practical_gate') {
    return `Weak ${titleCase(observation.involved_criteria?.[0] ?? 'criteria')} appears associated with non-approval.`;
  }
  if (observation.observation_type === 'discounted_risk') {
    const factors = observation.involved_factors ?? [];
    if (factors.length >= 2) return `The fund has accepted ${factors[0]} when paired with ${factors[1]}.`;
  }
  if (observation.observation_type === 'override_rate') {
    return `${formatObservationSegment(observation.segment)} records human overrides at a distinct rate.`;
  }
  if (observation.observation_type === 'mandate_behavior') {
    return 'Recorded recommendation and ruling agreement differs across thesis versions.';
  }
  if (observation.observation_type === 'recurring_factor') {
    return `The fund repeatedly cites ${formatObservationSegment(observation.segment).toLowerCase()}.`;
  }
  return `${formatObservationFamily(observation.observation_type)} appears repeatedly in the recorded decisions.`;
}

export function observationEvidenceLabel(observation: Pick<FundObservation, 'supporting_case_ids' | 'contradictory_case_ids'>): string {
  return `${observation.supporting_case_ids.length} supporting · ${observation.contradictory_case_ids.length} contradictory`;
}

export function sufficiencyLabel(value: string): string {
  return `${value.slice(0, 1).toUpperCase()}${value.slice(1)} basis`;
}
