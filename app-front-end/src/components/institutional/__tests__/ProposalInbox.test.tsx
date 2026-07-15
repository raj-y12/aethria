import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  fetchPolicyProposals: vi.fn(), fetchPolicyProposal: vi.fn(), previewPolicyProposal: vi.fn(),
  reviewPolicyProposal: vi.fn(), publishGovernedPolicy: vi.fn(), deriveOverridePatterns: vi.fn(),
}));
vi.mock('../../../api/fundIntelligence', async (original) => ({
  ...(await original<typeof import('../../../api/fundIntelligence')>()), ...api,
}));

import ProposalInbox from '../ProposalInbox';

const proposal = {
  policy_proposal_id: 'proposal-1', proposal_fingerprint: 'fingerprint-1',
  pattern_summary: 'Repeated policy disagreement on capital efficiency.',
  attribution: 'policy_criterion_disagreement', sample_size: 8, confidence: 0.78,
  limitations: ['Small emerging-manager sample.'], proposed_policy_patch: { capital_efficiency_weight: 0.2 },
  status: 'ready_for_review' as const, created_at: '2026-07-15T12:00:00Z', updated_at: '2026-07-15T12:00:00Z',
};

function renderInbox() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}><ProposalInbox fundConfig={{ stage: 'pre_seed' }} /></QueryClientProvider>);
}

describe('ProposalInbox governance', () => {
  beforeEach(() => {
    Object.values(api).forEach((mock) => mock.mockReset());
    api.fetchPolicyProposals.mockResolvedValue([proposal]);
    api.fetchPolicyProposal.mockResolvedValue({ proposal, signals: [], impact_previews: [], policy_versions: [] });
    api.previewPolicyProposal.mockResolvedValue({ affected_opportunity_count: 5, estimated_effect: { automatic_rescore: false }, limitations: [] });
    api.reviewPolicyProposal.mockResolvedValue({
      proposal: { ...proposal, status: 'accepted' },
      policy_version: { governed_policy_version_id: 'version-1', status: 'draft' },
      production_policy_changed: false,
    });
    api.publishGovernedPolicy.mockResolvedValue({ policy_version: { status: 'published' } });
  });

  it('labels learned changes as proposals, never as automatically applied mutations', async () => {
    renderInbox();
    expect(await screen.findByText('Repeated policy disagreement on capital efficiency.')).toBeInTheDocument();
    expect(screen.getByText('Ready for review')).toBeInTheDocument();
    expect(screen.queryByText(/automatically applied/i)).not.toBeInTheDocument();
  });

  it('requires impact preview and rationale before acceptance, then publishes separately', async () => {
    renderInbox();
    fireEvent.click(await screen.findByRole('button', { name: 'Review proposal' }));

    expect(screen.getByRole('button', { name: 'Accept proposal' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Run impact preview' }));
    expect(await screen.findByText(/5 opportunities/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Review rationale'), { target: { value: 'The pattern is attributable and material across the reviewed cohort.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Accept proposal' }));

    await waitFor(() => expect(api.reviewPolicyProposal).toHaveBeenCalledWith('proposal-1', {
      action: 'accept', rationale: 'The pattern is attributable and material across the reviewed cohort.',
    }));
    expect(await screen.findByText(/Production policy is unchanged/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Publish policy version' }));
    await waitFor(() => expect(api.publishGovernedPolicy).toHaveBeenCalledWith('version-1', { stage: 'pre_seed' }));
  });
});
