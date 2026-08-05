import { describe, expect, it } from 'vitest';
import { normalizeStructuredScoring } from '../reviewScoring';
import type {
  PresentationDimension,
  Review,
  ScoringDimension,
  ScoringDimensionKey,
  ScoringPresentation,
  StructuredScoring,
} from '../../types/startup';

const DIMENSION_KEYS: ScoringDimensionKey[] = [
  'market',
  'execution',
  'product',
  'technical',
  'defensibility',
];

function legacyDimension(score: number): ScoringDimension {
  return {
    score,
    confidence: 0.9,
    components: {
      legacy_signal: {
        score,
        label: 'Legacy signal',
        reasoning: 'Legacy source.',
      },
    },
  };
}

function legacyScoring(score: number): StructuredScoring {
  return {
    market: legacyDimension(score),
    execution: legacyDimension(score),
    product: legacyDimension(score),
    technical: legacyDimension(score),
    defensibility: legacyDimension(score),
    overall_score: score,
  };
}

function presentationDimension(key: ScoringDimensionKey, score: number): PresentationDimension {
  return {
    id: key,
    label: `${key} label`,
    score,
    band: 'Strong',
    headline: `${key} headline`,
    score_interpretation: `${key} interpretation`,
    analyst_summary: `${key} summary`,
    supports: [`${key} support`],
    weakens: [`${key} weakness`],
    missing_evidence: [],
    diligence_actions: [],
    confidence_label: 'Extensive',
    confidence_tooltip: 'Well supported',
    components: [
      {
        id: `${key}_signal`,
        label: `${key} signal`,
        score,
        band: 'Strong',
        has_evidence: true,
        interpretation: `${key} evidence`,
      },
    ],
  };
}

describe('normalizeStructuredScoring', () => {
  it('uses scoring_presentation ahead of every legacy structured score source', () => {
    const presentationScores = [9.1, 8.2, 7.3, 6.4, 5.5];
    const scoringPresentation: ScoringPresentation = {
      overall_score: 8.8,
      overall_band: 'Strong',
      confidence_label: 'Extensive',
      confidence_tooltip: 'Well supported',
      dimensions: DIMENSION_KEYS.map((key, index) => presentationDimension(key, presentationScores[index])),
    };
    const review: Review = {
      scoring_presentation: scoringPresentation,
      scoring: legacyScoring(1),
      structured_scoring: legacyScoring(2),
      score_breakdown: legacyScoring(3),
    };

    const result = normalizeStructuredScoring(review);

    expect(result).toMatchObject({
      overall_score: 8.8,
      market: { score: 9.1 },
      execution: { score: 8.2 },
      product: { score: 7.3 },
      technical: { score: 6.4 },
      defensibility: { score: 5.5 },
    });
    expect(result?.market).toMatchObject({
      reasoning: ['market summary', 'market support'],
      weaknesses: ['market weakness'],
      components: {
        market_signal: {
          score: 9.1,
          label: 'Strong',
          evidence: 'market evidence',
        },
      },
    });
  });
});
