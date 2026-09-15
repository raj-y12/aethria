import { fireEvent, render, screen } from '@testing-library/react';
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

describe('AssessmentScorecard accessibility and robustness', () => {
  it('explains a constrained Reviewer proposal without exposing lineage identifiers', () => {
    render(<AssessmentScorecard
      dimensions={DIMENSIONS} scoring={scoring()} reviewerRows={[]}
      reviewerConsensus={{ min: null, max: null, spread: null, split: false }}
      canonicalCriteria={[{
        criterion_assessment_id: 'internal-criterion', criterion: 'market', score: 6,
        confidence: 0.6, evidence_sufficiency: 'partial', reasoning: 'Demand is promising.',
        supporting_claim_ids: ['internal-claim'], contradicting_claim_ids: [],
        missing_evidence: [], quality_flags: [],
        deterministic_adjustments: { change_from_prior_review: {
          previous_score: 5, previous_reasoning: 'Demand had not been independently observed.',
          score_changed: true, reasoning_changed: true,
        }, assessment_validation: {
          reviewer_assessment_id: 'internal-assessment', proposed_score: 8, validated_score: 6,
          score_status: 'CAPPED', cap_reason: 'Limited independent market evidence.',
          contradiction_status: 'PRESENT',
        } },
      }]}
    />);
    fireEvent.click(screen.getByRole('button', { name: /Market/ }));
    expect(screen.getByText('Reviewer assessment: 8.0/10. Validated: 6.0/10.')).toBeInTheDocument();
    expect(screen.getByText('Limited independent market evidence.')).toBeInTheDocument();
    expect(screen.getByText('Conflicting evidence requires diligence.')).toBeInTheDocument();
    expect(screen.getByText('Previous review: 5.0/10.')).toBeInTheDocument();
    expect(screen.getByText('Previous reasoning: Demand had not been independently observed.')).toBeInTheDocument();
    expect(screen.queryByText(/lowest eligible policy anchor/)).not.toBeInTheDocument();
    expect(document.body.textContent).not.toContain('internal-assessment');
    expect(document.body.textContent).not.toContain('internal-claim');
    fireEvent.click(screen.getByRole('button', { name: 'How this was scored' }));
    expect(screen.getByText(/Reviewer proposes each dimension score/)).toBeInTheDocument();
    expect(screen.queryByText(/anchors low/)).not.toBeInTheDocument();
  });

  it('links each expandable dimension button to its detail panel via aria-controls', () => {
    const structured = scoring({
      market: dimension({ reasoning: ['A specific reason the score landed here.'] }),
    });
    render(
      <AssessmentScorecard
        dimensions={DIMENSIONS}
        scoring={structured}
        reviewerRows={[]}
        reviewerConsensus={{ min: null, max: null, spread: null, split: false }}
      />
    );

    const marketButton = screen.getByRole('button', { name: /Market/ });
    const controlsId = marketButton.getAttribute('aria-controls');
    expect(controlsId).toBeTruthy();
    expect(marketButton.getAttribute('aria-expanded')).toBe('false');

    fireEvent.click(marketButton);

    expect(marketButton.getAttribute('aria-expanded')).toBe('true');
    expect(document.getElementById(controlsId!)).toBeInTheDocument();
  });

  it('a row with nothing to expand has no aria-controls and stays disabled', () => {
    // A dimension with a plain score, no reasoning/components/flags at all has
    // hasDetail=false — it must not claim to control a panel that never renders.
    const structured = scoring({
      market: { score: 6, confidence: 0.9, components: {} },
    });
    render(
      <AssessmentScorecard
        dimensions={DIMENSIONS}
        scoring={structured}
        reviewerRows={[]}
        reviewerConsensus={{ min: null, max: null, spread: null, split: false }}
      />
    );

    const marketButton = screen.getByRole('button', { name: /Market/ });
    expect(marketButton).toBeDisabled();
    expect(marketButton.getAttribute('aria-controls')).toBeNull();
  });

  it('renders without error when every dimension is unscored and there are no reviewer rows', () => {
    const unscoredDim = dimension({ score: 0, unscored: true, components: {}, reasoning: null });
    const structured = scoring({
      market: unscoredDim,
      product: unscoredDim,
      technical: unscoredDim,
      execution: unscoredDim,
      defensibility: unscoredDim,
      overall_score: 0,
    });

    render(
      <AssessmentScorecard
        dimensions={DIMENSIONS}
        scoring={structured}
        reviewerRows={[]}
        reviewerConsensus={{ min: null, max: null, spread: null, split: false }}
      />
    );

    expect(screen.getAllByText('Not scored').length).toBe(5);
  });

  it('shows the evidence and rule behind a scored component', () => {
    const structured = scoring({
      market: dimension({
        components: {
          tam: {
            score: 7,
            confidence: 0.8,
            label: 'large',
            value: '$1B',
            reasoning: 'Market size is supported.',
            evidence: 'Independent market report.',
            rule: 'Sector benchmark threshold.',
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

    fireEvent.click(screen.getByRole('button', { name: /Market/ }));
    expect(screen.getByText(/Market 6\.0 \+ Product 6\.0 \+ Technical 6\.0 \+ Execution 6\.0/)).toBeInTheDocument();
    expect(screen.getByText('7.0/10 · 80% confidence')).toBeInTheDocument();
    expect(screen.getByText('Evidence: Independent market report.')).toBeInTheDocument();
    expect(screen.getByText('Rule: Sector benchmark threshold.')).toBeInTheDocument();
  });

  it('renders the canonical formula and cited source beside its score', () => {
    render(
      <AssessmentScorecard
        dimensions={DIMENSIONS}
        scoring={scoring()}
        reviewerRows={[]}
        reviewerConsensus={{ min: null, max: null, spread: null, split: false }}
        canonicalCriteria={[{
          criterion_assessment_id: 'criterion-market',
          criterion: 'market', score: 3, confidence: 0.8,
          evidence_sufficiency: 'sufficient', reasoning: 'A constraint is verified.',
          supporting_claim_ids: ['claim-market'], contradicting_claim_ids: [],
          missing_evidence: [], quality_flags: [],
          deterministic_adjustments: { aggregation: 'lowest_eligible_claim_score', eligible_anchor_scores: [3, 8] },
        }]}
        canonicalClaims={[{
          claimId: 'claim-market', criterion: 'market', relationship: 'supports',
          provenance: 'verified', claim: 'Market access is constrained by a verified rule.',
          sources: [{ artifactId: 'source-1', title: 'Regulator notice', href: 'https://example.com/notice' }],
        }]}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Market/ }));
    expect(screen.getByText('Score ledger')).toBeInTheDocument();
    expect(screen.getByText(/Formula: lowest eligible policy anchor \(3, 8\)\. Result: 3\.0\/10/)).toBeInTheDocument();
    expect(screen.getByText(/Supports: Market access is constrained/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Regulator notice' })).toHaveAttribute('href', 'https://example.com/notice');
  });

  it('withholds the overall headline when canonical evidence is insufficient', () => {
    render(
      <AssessmentScorecard
        dimensions={DIMENSIONS}
        scoring={scoring()}
        reviewerRows={[]}
        reviewerConsensus={{ min: null, max: null, spread: null, split: false }}
        canonicalRecommendationState="insufficient_evidence"
      />
    );

    expect(screen.getByText('Not scored')).toBeInTheDocument();
    expect(screen.getByText(/Decision blocked by evidence/)).toBeInTheDocument();
    expect(screen.getByText(/Incomplete evidence/)).toBeInTheDocument();
    expect(screen.queryByText(/Strong evidence/)).not.toBeInTheDocument();
    expect(screen.getByText(/No headline score is shown because required evidence is missing/)).toBeInTheDocument();
  });

  it('explains historical scoring without exposing internal rubric identifiers', () => {
    render(
      <AssessmentScorecard
        dimensions={DIMENSIONS}
        scoring={scoring()}
        reviewerRows={[]}
        reviewerConsensus={{ min: null, max: null, spread: null, split: false }}
        canonicalRubricVersion="2.0"
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'How this was scored' }));
    expect(screen.getByText(/Historical evidence-based scoring/)).toBeInTheDocument();
    expect(screen.queryByText(/Rubric: 2.0/)).not.toBeInTheDocument();
  });
});

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

describe('AssessmentScorecard reviewer panel honesty', () => {
  it('discloses that the reviewer panel is one model over shared evidence, not independent reviews', () => {
    render(
      <AssessmentScorecard
        dimensions={DIMENSIONS}
        scoring={scoring()}
        reviewerRows={[{ key: 'SkepticalReviewer', name: 'Skeptical', score: 5, take: 'A read.' }]}
        reviewerConsensus={{ min: 5, max: 5, spread: 0, split: false }}
      />
    );

    expect(
      screen.getByText('One model, one evidence packet, three prompted postures — not independent reviews.')
    ).toBeInTheDocument();
  });

  it('names each persona\'s prompted posture on its row', () => {
    render(
      <AssessmentScorecard
        dimensions={DIMENSIONS}
        scoring={scoring()}
        reviewerRows={[{ key: 'SkepticalReviewer', name: 'Skeptical', score: 5, take: 'A read.' }]}
        reviewerConsensus={{ min: 5, max: 5, spread: 0, split: false }}
      />
    );

    expect(screen.getByText('Skeptical').getAttribute('title')).toMatch(/assume the worst/);
  });

  it('never presents a reviewer verdict as the fallback qualitative read', () => {
    render(
      <AssessmentScorecard
        dimensions={DIMENSIONS}
        scoring={scoring()}
        reviewerRows={[{ key: 'DefaultReviewer', name: 'Balanced', score: 5, verdict: 'STRONG' }]}
        reviewerConsensus={{ min: 5, max: 5, spread: 0, split: false, verdict: 'STRONG' }}
      />
    );

    expect(screen.queryByText(/STRONG/)).not.toBeInTheDocument();
    expect(screen.getByText('No qualitative summary.')).toBeInTheDocument();
  });
});
