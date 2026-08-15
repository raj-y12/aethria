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
  it('presents one decision region with status distinct from the subordinate system lean', () => {
    render(<MemoDecisionBrief brief={brief} />);

    const region = screen.getByRole('region', { name: 'Decision brief' });
    expect(within(region).getByRole('heading', { name: 'Decision brief' })).toBeInTheDocument();
    expect(within(region).getByText('Ready for ruling')).toBeInTheDocument();
    expect(within(region).getByText('System lean')).toBeInTheDocument();
    expect(within(region).getByText('Advance')).toBeInTheDocument();
    expect(within(region).getByText('Mandate')).toBeInTheDocument();
    expect(within(region).getByText('Evidence')).toBeInTheDocument();
    expect(within(region).getByText('Reviewer state')).toBeInTheDocument();
    expect(region).not.toHaveTextContent(/\d+(?:\.\d+)?%|confidence/i);
  });

  it('keeps claim source links while rejecting source rendering on the grouped risk surface', () => {
    render(<MemoDecisionBrief brief={brief} />);

    const region = screen.getByRole('region', { name: 'Decision brief' });
    const driver = within(region).getByText('Customer pull is sustained.').closest('li');
    expect(driver).not.toBeNull();
    expect(within(driver!).getByText('Rule-derived')).toBeInTheDocument();
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
    expect(within(risk!).getByText('Source missing')).toBeInTheDocument();
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
    expect(within(risk!).getByText('Source missing')).toBeInTheDocument();
  });

  it('names unavailable decision data instead of rendering a categorical verdict', () => {
    render(
      <MemoDecisionBrief
        brief={{ ...brief, status: 'unavailable', lean: 'none', leanProvenance: 'missing' }}
        stateMessage="The canonical evaluation could not be loaded."
      />,
    );

    const region = screen.getByRole('region', { name: 'Decision status' });
    expect(within(region).getByRole('status')).toHaveTextContent('Decision data unavailable');
    expect(within(region).getByText('The canonical evaluation could not be loaded.')).toBeInTheDocument();
    expect(within(region).queryByRole('heading', { name: 'Decision brief' })).not.toBeInTheDocument();
    expect(within(region).queryByText('System lean')).not.toBeInTheDocument();
    expect(within(region).queryByText('Unknown')).not.toBeInTheDocument();
    expect(region).not.toHaveTextContent(/invest|pass|monitor/i);
  });

  it('names an evidence block explicitly', () => {
    render(<MemoDecisionBrief brief={{ ...brief, status: 'blocked' }} />);

    expect(screen.getByText('Blocked by evidence')).toBeInTheDocument();
    expect(screen.queryByText('Blocked', { exact: true })).not.toBeInTheDocument();
  });
});
