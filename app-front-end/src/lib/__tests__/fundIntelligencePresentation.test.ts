import { describe, expect, it } from 'vitest';
import {
  formatObservationFamily,
  observationEvidenceLabel,
  selectLeadHypothesis,
  selectLeadObservation,
} from '../fundIntelligencePresentation';
import type { FundHypothesis, FundObservation } from '../../api/fundIntelligence';

function observation(overrides: Partial<FundObservation> = {}): FundObservation {
  return {
    observation_id: 'observation-1',
    observation_type: 'recurring_factor',
    segment: { scope: 'fund' },
    supporting_case_ids: ['evaluation-1', 'evaluation-2'],
    contradictory_case_ids: ['evaluation-3'],
    sample_size: 3,
    time_window: { from: '2026-01-01T00:00:00Z', to: '2026-03-01T00:00:00Z' },
    thesis_versions: ['thesis-1'],
    mandate_versions: ['thesis-1'],
    policy_versions: ['policy-1'],
    metric: { count: 3 },
    sufficiency: 'emerging',
    descriptive_confidence: 0.55,
    limitations: ['Descriptive association only.'],
    interpretation_as_of: 'none_available',
    interpretation_provenance: [],
    ...overrides,
  };
}

function hypothesis(overrides: Partial<FundHypothesis> = {}): FundHypothesis {
  return {
    hypothesis_id: 'hypothesis-1',
    hypothesis_family: 'segment_specific_behavior',
    statement: 'The fund behaves differently in infrastructure.',
    source_observation_ids: ['observation-1'],
    source_observation_types: ['override_rate'],
    segment: { dimension: 'sector', value: 'infrastructure' },
    supporting_case_ids: ['evaluation-1'],
    contradictory_case_ids: ['evaluation-2'],
    sample_size: 3,
    sufficiency: 'moderate',
    descriptive_confidence: 0.75,
    mandate_versions: ['thesis-1'],
    thesis_versions: ['thesis-1'],
    policy_versions: ['policy-1'],
    time_window: { from: '2026-01-01T00:00:00Z', to: '2026-03-01T00:00:00Z' },
    limitations: ['This is descriptive.'],
    status: 'descriptive_hypothesis',
    ...overrides,
  };
}

describe('Fund Intelligence presentation logic', () => {
  it('selects a lead observation deterministically from transparent signal strength', () => {
    const result = selectLeadObservation([
      observation({ observation_id: 'emerging-tradeoff', observation_type: 'criterion_tradeoff' }),
      observation({
        observation_id: 'moderate-gate',
        observation_type: 'practical_gate',
        sufficiency: 'moderate',
        sample_size: 6,
      }),
      observation({
        observation_id: 'strong-factor',
        sufficiency: 'strong',
        sample_size: 5,
      }),
    ]);

    expect(result?.observation_id).toBe('strong-factor');
  });

  it('uses family priority as a deterministic tie-breaker after evidence strength', () => {
    const result = selectLeadObservation([
      observation({ observation_id: 'factor-a', observation_type: 'recurring_factor', sufficiency: 'moderate', sample_size: 6 }),
      observation({ observation_id: 'tradeoff-b', observation_type: 'criterion_tradeoff', sufficiency: 'moderate', sample_size: 6 }),
    ]);

    expect(result?.observation_id).toBe('tradeoff-b');
  });

  it('selects the strongest hypothesis without treating it as a causal ranking', () => {
    const result = selectLeadHypothesis([
      hypothesis({ hypothesis_id: 'emerging', sufficiency: 'emerging', sample_size: 4 }),
      hypothesis({ hypothesis_id: 'strong', sufficiency: 'strong', sample_size: 10 }),
    ]);

    expect(result?.hypothesis_id).toBe('strong');
  });

  it('translates backend family names into partner-facing language', () => {
    expect(formatObservationFamily('criterion_tradeoff')).toBe('Criterion trade-off');
    expect(formatObservationFamily('practical_gate')).toBe('Practical gate');
    expect(formatObservationFamily('mandate_behavior')).toBe('Mandate behavior');
  });

  it('keeps support and contradiction visible as evidence context', () => {
    expect(observationEvidenceLabel(observation())).toBe('2 supporting · 1 contradictory');
  });
});
