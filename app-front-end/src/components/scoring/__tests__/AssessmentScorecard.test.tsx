import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import AssessmentScorecard, { type ScorecardDimensionDef } from '../AssessmentScorecard';
import type { PresentationDimension, ScoringDimension, ScoringPresentation, StructuredScoring } from '../../../types/startup';

const DIMENSIONS: ScorecardDimensionDef[] = [
  { key: 'market', label: 'Market', id: 'market' },
  { key: 'product', label: 'Product', id: 'product' },
  { key: 'technical', label: 'Technical', id: 'technical' },
  { key: 'execution', label: 'Execution', id: 'execution' },
  { key: 'defensibility', label: 'Defensibility', id: 'defensibility' },
];

function dimension(overrides: Partial<ScoringDimension> = {}): ScoringDimension {
  return {
    score: 6,
    confidence: 0.7,
    components: {},
    reasoning: ['Solid evidence.'],
    ...overrides,
  };
}

function scoring(overrides: Partial<StructuredScoring> = {}): StructuredScoring {
  const base = dimension();
  return {
    market: base,
    product: base,
    technical: base,
    execution: base,
    defensibility: base,
    overall_score: 6,
    overall_confidence: 0.7,
    ...overrides,
  };
}

describe('AssessmentScorecard persona-divergence flag', () => {
  it('flags a dimension whose personas materially diverged', () => {
    const structured = scoring({
      market: dimension({
        score: 5.1,
        components: {
          persona_resolution: {
            score: 0,
            reasoning: '',
            strategy: 'conservative_mean_floor',
            spread: 6,
          },
        },
      }),
    });

    render(
      <AssessmentScorecard
        dimensions={DIMENSIONS}
        scoring={structured}
        reviewerRows={[]}
        reviewerConsensus={{ min: null, max: null, spread: null, split: false }}
      />
    );

    expect(screen.getByText('personas diverged')).toBeInTheDocument();
  });

  it('does not flag a dimension where personas agreed', () => {
    const structured = scoring({
      market: dimension({
        score: 6,
        components: {
          persona_resolution: { score: 0, reasoning: '', strategy: 'mean', spread: 0.5 },
        },
      }),
    });

    render(
      <AssessmentScorecard
        dimensions={DIMENSIONS}
        scoring={structured}
        reviewerRows={[]}
        reviewerConsensus={{ min: null, max: null, spread: null, split: false }}
      />
    );

    expect(screen.queryByText('personas diverged')).not.toBeInTheDocument();
  });

  it('flags divergence even when the legacy presentation overlay is active', () => {
    // Regression: live-verified against Manna Air Delivery, whose canonical evaluation was
    // unavailable so the legacy `scoring_presentation` overlay renders instead. The overlay's
    // generic "constrained by insufficient evidence" text must not swallow the persona flag.
    const structured = scoring({
      technical: dimension({
        score: 3.9,
        components: {
          persona_resolution: {
            score: 0,
            reasoning: '',
            strategy: 'conservative_mean_floor',
            spread: 2.3,
          },
        },
      }),
    });
    const presDim: PresentationDimension = {
      id: 'technical',
      label: 'Technical',
      score: 3.9,
      band: 'Concerning',
      headline: 'Technical',
      score_interpretation: 'Technical assessment is constrained by insufficient evidence across key criteria.',
      analyst_summary: 'Technical assessment is constrained by insufficient evidence across key criteria.',
      supports: [],
      weakens: [],
      missing_evidence: [],
      diligence_actions: [],
      confidence_label: 'Limited',
      confidence_tooltip: '',
      components: [],
    };
    const presentation: ScoringPresentation = {
      overall_score: 5.1,
      overall_band: 'Promising, incomplete',
      confidence_label: 'Limited evidence',
      confidence_tooltip: '',
      dimensions: [presDim],
    };

    render(
      <AssessmentScorecard
        dimensions={DIMENSIONS}
        scoring={structured}
        presentation={presentation}
        reviewerRows={[]}
        reviewerConsensus={{ min: null, max: null, spread: null, split: false }}
      />
    );

    expect(screen.getByText('personas diverged')).toBeInTheDocument();
  });
});
