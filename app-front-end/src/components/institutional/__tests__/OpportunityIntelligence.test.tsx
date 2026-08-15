import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  fetchOpportunityByLegacyStartup: vi.fn(),
  fetchEvidenceLedger: vi.fn(), correctClaim: vi.fn(), createEvidencePlan: vi.fn(),
  fetchCurrentEvaluation: vi.fn(),
  createHumanRuling: vi.fn(), listHumanRulings: vi.fn(),
}));

vi.mock('../../../api/identity', async (original) => ({ ...(await original<typeof import('../../../api/identity')>()),
  fetchOpportunityByLegacyStartup: api.fetchOpportunityByLegacyStartup,
}));
vi.mock('../../../api/evidence', async (original) => ({ ...(await original<typeof import('../../../api/evidence')>()),
  fetchEvidenceLedger: api.fetchEvidenceLedger, correctClaim: api.correctClaim, createEvidencePlan: api.createEvidencePlan,
}));
vi.mock('../../../api/evaluations', async (original) => ({ ...(await original<typeof import('../../../api/evaluations')>()),
  fetchCurrentEvaluation: api.fetchCurrentEvaluation,
}));
vi.mock('../../../api/decisions', async (original) => ({ ...(await original<typeof import('../../../api/decisions')>()),
  createHumanRuling: api.createHumanRuling, listHumanRulings: api.listHumanRulings,
}));

import OpportunityIntelligence from '../OpportunityIntelligence';

function seedApi() {
  api.fetchOpportunityByLegacyStartup.mockResolvedValue({
    opportunity_id: 'opportunity-1', company_id: 'company-1', context_key: 'primary', decision_state: 'monitor',
    service_level: 3, legacy_startup_id: 'startup-1', current_evaluation_id: 'evaluation-1',
    current_recommendation_id: 'recommendation-1', current_ruling_id: null,
    created_at: '2026-07-15T12:00:00Z', updated_at: '2026-07-15T12:00:00Z',
  });
  api.fetchEvidenceLedger.mockResolvedValue({
    artifacts: [{ artifact_id: 'artifact-1', artifact_type: 'interview_note', title: 'Founder interview', source_uri: 'https://example.com/founder-interview', trust_class: 'founder', access_class: 'tenant_confidential' }],
    items: [{ evidence_item_id: 'item-1', artifact_id: 'artifact-1', item_type: 'interview_quote', display_excerpt: 'Shipped the first workflow in nine days after six customer interviews.', verification_state: 'verified', source_quality: 0.8, extraction_confidence: 0.9 }],
    claims: [{ claim_id: 'claim-1', company_id: 'company-1', opportunity_id: 'opportunity-1', claim_type: 'founder_speed', display_text: 'Built and shipped the first workflow in nine days.', assertion_class: 'founder_asserted', confidence: 0.82, material: true, status: 'current' }],
    links: [{ link_id: 'link-1', claim_id: 'claim-1', evidence_item_id: 'item-1', relationship: 'supports', support_strength: 0.8, rationale: 'Direct interview evidence.' }],
    plans: [],
  });
  api.fetchCurrentEvaluation.mockResolvedValue({
    evaluation: {
      evaluation_id: 'evaluation-1', policy_version_id: 'policy-v3', policy_hash: 'policy-hash-v3', rubric_version: 'rubric-v2',
      partner_rules_version: 'rules-v1', partner_rules_hash: 'rules-hash-v1',
      model_manifest: { model_id: 'gpt-5-nano' }, prompt_manifest: { prompt_version: 'prompt-a' },
    },
    criteria: [{
      criterion_assessment_id: 'criterion-1', criterion: 'founder', score: 7, confidence: 0.8,
      evidence_sufficiency: 'sufficient', reasoning: 'Direct founder evidence.',
      supporting_claim_ids: ['claim-1'], contradicting_claim_ids: [], missing_evidence: [], quality_flags: [],
    }],
    recommendation: {
      recommendation_id: 'recommendation-1', recommended_state: 'monitor',
      decision_drivers: ['Customer pull is promising.'], principal_risks: ['Retention evidence remains missing.'],
      mandate_conflicts: [], missing_information: ['Net retention'], change_conditions: ['Verify three-month retention.'],
      human_review_required: true, confidence: 0.68,
    },
  });
  api.listHumanRulings.mockResolvedValue([{
    ruling_id: 'ruling-previous', opportunity_id: 'opportunity-1', recommendation_id: 'recommendation-1',
    decision: 'monitor', rationale: 'Wait for three months of verified retention before advancing.',
    investor_confidence: 0.72, override_type: 'timing', actor_id: 'user-1',
    created_at: '2026-07-16T12:00:00Z',
  }]);
  api.createHumanRuling.mockResolvedValue({ ruling_id: 'ruling-1', decision: 'monitor' });
}

function renderWorkspace() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <OpportunityIntelligence startupId="startup-1" />
    </QueryClientProvider>,
  );
}

describe('OpportunityIntelligence', () => {
  beforeEach(() => { Object.values(api).forEach((mock) => mock.mockReset()); seedApi(); });

  it('is one decision brief with status, system lean, and ruling action in the same work surface', async () => {
    renderWorkspace();
    const brief = await screen.findByRole('region', { name: 'Decision brief' });
    expect(within(brief).getByRole('heading', { name: 'Decision brief' })).toBeInTheDocument();
    expect(await within(brief).findByText('Ruling recorded')).toBeInTheDocument();
    expect(within(brief).getByText('System lean')).toBeInTheDocument();
    expect(within(brief).getByText('Monitor', { selector: 'strong' })).toBeInTheDocument();
    expect(within(brief).getByLabelText('Make your ruling')).toBeInTheDocument();
    expect(screen.queryByRole('tab')).not.toBeInTheDocument();
    expect(screen.queryByText(/current status/i)).not.toBeInTheDocument();
    expect(screen.queryByText('opportunity-1')).not.toBeInTheDocument();
    expect(screen.queryByText(/policy-v3|policy-hash-v3|prompt-a/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/keep watching|company identity|artifact hash|storage reference/i)).not.toBeInTheDocument();
  });

  it('shows decision drivers and inline provenance while keeping the evidence ledger available on demand', async () => {
    renderWorkspace();
    expect(await screen.findByText('Customer pull is promising.')).toBeInTheDocument();
    expect(screen.getByText('Retention evidence remains missing.')).toBeInTheDocument();
    expect(screen.getByText('Reported')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Founder interview' })).toHaveAttribute('href', 'https://example.com/founder-interview');
    expect(screen.queryByText(/% confidence/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('Review supporting evidence'));
    const founderSignals = await screen.findByLabelText('Founder evidence signals');
    expect(within(founderSignals).getByText('Built and shipped the first workflow in nine days.')).toBeInTheDocument();
    expect(within(founderSignals).getByText('Shipped the first workflow in nine days after six customer interviews.')).toBeInTheDocument();
    expect(screen.queryByLabelText('Evidence-backed founder signals')).not.toBeInTheDocument();
    expect(screen.queryByText(/magnetic founder/i)).not.toBeInTheDocument();
  });

  it('keeps the decision brief and evidence visible in read-only mode while hiding the composer', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <OpportunityIntelligence startupId="startup-1" readOnly />
      </QueryClientProvider>,
    );

    const brief = await screen.findByRole('region', { name: 'Decision brief' });
    expect(await within(brief).findByText('Customer pull is promising.')).toBeInTheDocument();
    expect(within(brief).getByText('Review supporting evidence')).toBeInTheDocument();
    expect(within(brief).queryByLabelText('Make your ruling')).not.toBeInTheDocument();
  });

  it('keeps the latest recorded ruling and rationale visible', async () => {
    renderWorkspace();
    const history = await screen.findByLabelText('Ruling history');
    expect(within(history).getByText('Latest recorded ruling')).toBeInTheDocument();
    expect(within(history).getByText('Monitor')).toBeInTheDocument();
    expect(within(history).getByText('Wait for three months of verified retention before advancing.')).toBeInTheDocument();
    expect(within(history).getByText('Timing')).toBeInTheDocument();
  });

  it('keeps decision data loading until authoritative ruling history resolves', async () => {
    let resolveRulings!: (rulings: []) => void;
    api.listHumanRulings.mockReturnValue(new Promise<[]>(resolve => { resolveRulings = resolve; }));

    renderWorkspace();

    await waitFor(() => {
      expect(api.fetchCurrentEvaluation).toHaveBeenCalledOnce();
      expect(api.fetchEvidenceLedger).toHaveBeenCalledOnce();
      expect(api.listHumanRulings).toHaveBeenCalledOnce();
    });
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByText('Decision data loading')).toBeInTheDocument();
    expect(screen.queryByLabelText('Make your ruling')).not.toBeInTheDocument();

    await act(async () => { resolveRulings([]); });
    expect(await screen.findByText('Ready for ruling')).toBeInTheDocument();
    expect(screen.getByLabelText('Make your ruling')).toBeInTheDocument();
  });

  it('treats a ruling-history error as unavailable decision data and hides the composer', async () => {
    api.listHumanRulings.mockRejectedValue(new Error('ruling store unavailable'));

    renderWorkspace();

    expect(await screen.findByText('Decision data unavailable')).toBeInTheDocument();
    expect(screen.getByText('The ruling history could not be loaded.')).toBeInTheDocument();
    expect(screen.queryByLabelText('Make your ruling')).not.toBeInTheDocument();
  });

  it('requires a rationale before recording a human ruling', async () => {
    renderWorkspace();
    fireEvent.click(await screen.findByRole('button', { name: 'Monitor' }));
    expect(screen.getByRole('button', { name: 'Review ruling' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Ruling rationale'), { target: { value: 'Customer pull is credible; monitor until retention is verified.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Review ruling' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Commit this ruling' }));
    await waitFor(() => expect(api.createHumanRuling).toHaveBeenCalledWith('opportunity-1', expect.objectContaining({
      decision: 'monitor', rationale: 'Customer pull is credible; monitor until retention is verified.',
    })));
  });

  it('asks why only when the ruling goes against the recommendation', async () => {
    renderWorkspace();
    await screen.findByText('Customer pull is promising.');
    // Monitor matches the system lean — no override question.
    fireEvent.click(screen.getByRole('button', { name: 'Monitor' }));
    expect(screen.queryByLabelText('Override attribution')).not.toBeInTheDocument();
    // Pass disagrees — the question appears and the answer is sent with the ruling.
    fireEvent.click(screen.getByRole('button', { name: 'Pass' }));
    fireEvent.change(screen.getByLabelText('Override attribution'), { target: { value: 'missing_private_evidence' } });
    fireEvent.change(screen.getByLabelText('Ruling rationale'), { target: { value: 'Spoke with two design partners directly.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Review ruling' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Commit this ruling' }));
    await waitFor(() => expect(api.createHumanRuling).toHaveBeenCalledWith('opportunity-1', expect.objectContaining({
      decision: 'pass', override_type: 'missing_private_evidence',
    })));
  });

  it('keeps an insufficient-evidence recommendation visible with its gaps and change conditions', async () => {
    api.fetchCurrentEvaluation.mockResolvedValue({
      evaluation: {},
      criteria: [],
      recommendation: {
        recommendation_id: 'recommendation-1', recommended_state: 'insufficient_evidence',
        decision_drivers: [], principal_risks: [], mandate_conflicts: [],
        missing_information: ['Verified market demand'],
        change_conditions: ['Resolve missing evidence: market.'],
        human_review_required: true, confidence: 0,
      },
    });
    api.fetchEvidenceLedger.mockResolvedValue({ artifacts: [], items: [], claims: [], links: [], plans: [] });
    renderWorkspace();
    expect(await screen.findByRole('button', { name: 'Review ruling' })).toBeInTheDocument();
    expect(await screen.findByText('Blocked by evidence')).toBeInTheDocument();
    expect(screen.getByText('No system lean')).toBeInTheDocument();
    expect(screen.getByText('Verified market demand')).toBeInTheDocument();
    expect(screen.getByText('Resolve missing evidence: market.')).toBeInTheDocument();
    expect(screen.queryByText('Review supporting evidence')).not.toBeInTheDocument();
    expect(screen.getByText(/canonical evaluation is blocked by missing evidence/i)).toBeInTheDocument();
  });
});
