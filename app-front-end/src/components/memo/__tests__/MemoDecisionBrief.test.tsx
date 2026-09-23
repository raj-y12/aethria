import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { MemoDecisionBrief as MemoDecisionBriefModel } from '../../../lib/memoDecisionBrief';
import MemoDecisionBrief from '../MemoDecisionBrief';

const brief: MemoDecisionBriefModel = {
  status: 'ready_for_ruling',
  lean: 'advance',
  leanProvenance: 'rule-derived',
  mandate: 'unknown',
  coverage: 'sufficient',
  agreement: 'contested',
  ruling: null,
  drivers: ['Customer pull is sustained.', 'Founder velocity is verified.'],
  claims: [{
    claimId: 'claim-1',
    claim: 'Three customers renewed after the pilot.',
    criterion: 'traction',
    relationship: 'supports',
    provenance: 'verified',
    sources: [{
      artifactId: 'artifact-1',
      title: 'Customer renewal register',
      href: 'https://example.com/renewals',
    }],
  }],
  derivations: [{ criterion: 'fund_fit', provenance: 'rule-derived' }],
  risks: [{
    key: 'regulatory-expansion',
    text: 'Expansion requires regulatory approval.',
    kind: 'risk',
    severity: 'high',
  }],
};

describe('MemoDecisionBrief', () => {
  it('keeps long source excerpts behind an expandable control', () => {
    render(<MemoDecisionBrief brief={{ ...brief, claims: [{ ...brief.claims[0],
      claim: 'Retrieved source text. '.repeat(40),
    }] }} />);
    const disclosure = screen.getByText('Read source excerpt').closest('details');
    expect(disclosure).not.toHaveAttribute('open');
    expect(screen.getByRole('link', { name: 'Customer renewal register' })).toBeVisible();
  });
  it('attributes new analysis risks to the review and evidence checks', () => {
    render(<MemoDecisionBrief brief={{ ...brief, leanProvenance: 'partner-judgment' }} />);
    const risk = screen.getByText('Expansion requires regulatory approval.').closest('li');
    expect(within(risk!).getByText('Review and evidence checks')).toBeInTheDocument();
    expect(within(risk!).queryByText('Rule-derived')).not.toBeInTheDocument();
  });
  it('presents the evidence-coverage region right before the ruling — no lean, mandate, or reviewer tiles', () => {
    render(<MemoDecisionBrief brief={brief} />);

    const region = screen.getByRole('region', { name: 'Evidence coverage' });
    expect(within(region).getByRole('heading', { name: 'Evidence coverage' })).toBeInTheDocument();
    expect(within(region).getByText('Ready for ruling')).toBeInTheDocument();
    // System lean, mandate, and reviewer-state now live on the masthead and Thesis alignment.
    // The Evidence tile is gone too — it could never say anything the status line hadn't already said.
    expect(within(region).queryByText('System lean')).not.toBeInTheDocument();
    expect(within(region).queryByText('Mandate')).not.toBeInTheDocument();
    expect(within(region).queryByText('Reviewer state')).not.toBeInTheDocument();
    expect(within(region).queryByText('Evidence')).not.toBeInTheDocument();
    // Decision drivers now live under Assessment, not here.
    expect(within(region).queryByText('Decision drivers')).not.toBeInTheDocument();
    expect(within(region).queryByText('Customer pull is sustained.')).not.toBeInTheDocument();
    expect(region).not.toHaveTextContent(/\d+(?:\.\d+)?%|confidence/i);
  });

  it('keeps claim source links while rejecting source rendering on the grouped risk surface', () => {
    render(<MemoDecisionBrief brief={brief} />);

    const region = screen.getByRole('region', { name: 'Evidence coverage' });
    const claim = within(region).getByText('Three customers renewed after the pilot.').closest('li');
    expect(claim).not.toBeNull();
    expect(within(claim!).getByText('Supports')).toBeInTheDocument();
    expect(within(claim!).getByText('Verified')).toBeInTheDocument();
    expect(within(region).getByRole('link', { name: 'Customer renewal register' })).toHaveAttribute(
      'href',
      'https://example.com/renewals',
    );
    expect(within(region).getByRole('heading', { name: 'Risks and evidence gaps' })).toBeInTheDocument();
    const risk = within(region).getByText('Expansion requires regulatory approval.').closest('li');
    expect(risk).not.toBeNull();
    expect(within(risk!).getByText('Rule-derived')).toBeInTheDocument();
    expect(within(risk!).queryByText('Source missing')).not.toBeInTheDocument();
    expect(within(region).queryByRole('link', { name: 'Regulator guidance' })).not.toBeInTheDocument();
    expect(region).not.toHaveTextContent(/reviewer score spread|gap >=/i);
  });

  it('distinguishes contradicting claims and names missing sources on their material item', () => {
    render(
      <MemoDecisionBrief
        brief={{
          ...brief,
          claims: [{
            ...brief.claims[0],
            claim: 'The renewal claim is disputed.',
            relationship: 'contradicts',
            provenance: 'missing',
            sources: [],
          }],
          risks: [{
            ...brief.risks[0],
            text: 'Regulatory evidence has not been sourced.',
          }],
        }}
      />,
    );

    const claim = screen.getByText('The renewal claim is disputed.').closest('li');
    expect(claim).not.toBeNull();
    expect(within(claim!).getByText('Contradicts')).toBeInTheDocument();
    expect(within(claim!).getByText('Source missing')).toBeInTheDocument();

    const risk = screen.getByText('Regulatory evidence has not been sourced.').closest('li');
    expect(risk).not.toBeNull();
    expect(within(risk!).getByText('Rule-derived')).toBeInTheDocument();
    expect(within(risk!).queryByText('Source missing')).not.toBeInTheDocument();
  });

  it('names unavailable decision data instead of rendering a categorical verdict', () => {
    render(
      <MemoDecisionBrief
        brief={{ ...brief, status: 'unavailable', lean: 'none', leanProvenance: 'missing' }}
        stateMessage="The decision record could not be loaded."
      />,
    );

    const region = screen.getByRole('region', { name: 'Evidence coverage' });
    expect(within(region).getByText('Decision data unavailable')).toBeInTheDocument();
    expect(within(region).getByText('The decision record could not be loaded.')).toBeInTheDocument();
    expect(region).not.toHaveTextContent(/invest|pass|monitor/i);
  });

  it('names an evidence block explicitly', () => {
    render(<MemoDecisionBrief brief={{ ...brief, status: 'blocked' }} />);

    expect(screen.getByText('Blocked by evidence')).toBeInTheDocument();
    expect(screen.queryByText('Blocked', { exact: true })).not.toBeInTheDocument();
  });
});
