import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  fetchOpportunityByLegacyStartup: vi.fn(), fetchCompany: vi.fn(), fetchObservations: vi.fn(),
  fetchEvidenceLedger: vi.fn(), correctClaim: vi.fn(), createEvidencePlan: vi.fn(),
  fetchCurrentEvaluation: vi.fn(), evaluateOpportunity: vi.fn(),
  createHumanRuling: vi.fn(), listWorkflowActions: vi.fn(), createWorkflowAction: vi.fn(), approveWorkflowAction: vi.fn(),
  fetchMonitoringStatus: vi.fn(), requestEvidenceRefresh: vi.fn(), setOpportunityServiceLevel: vi.fn(),
  registerConfidentialArtifact: vi.fn(),
}));

vi.mock('../../../api/identity', async (original) => ({ ...(await original<typeof import('../../../api/identity')>()),
  fetchOpportunityByLegacyStartup: api.fetchOpportunityByLegacyStartup, fetchCompany: api.fetchCompany,
  fetchObservations: api.fetchObservations,
}));
vi.mock('../../../api/evidence', async (original) => ({ ...(await original<typeof import('../../../api/evidence')>()),
  fetchEvidenceLedger: api.fetchEvidenceLedger, correctClaim: api.correctClaim, createEvidencePlan: api.createEvidencePlan,
}));
vi.mock('../../../api/evaluations', async (original) => ({ ...(await original<typeof import('../../../api/evaluations')>()),
  fetchCurrentEvaluation: api.fetchCurrentEvaluation, evaluateOpportunity: api.evaluateOpportunity,
}));
vi.mock('../../../api/decisions', async (original) => ({ ...(await original<typeof import('../../../api/decisions')>()),
  createHumanRuling: api.createHumanRuling, listWorkflowActions: api.listWorkflowActions,
  createWorkflowAction: api.createWorkflowAction, approveWorkflowAction: api.approveWorkflowAction,
}));
vi.mock('../../../api/monitoring', async (original) => ({ ...(await original<typeof import('../../../api/monitoring')>()),
  fetchMonitoringStatus: api.fetchMonitoringStatus, requestEvidenceRefresh: api.requestEvidenceRefresh,
  setOpportunityServiceLevel: api.setOpportunityServiceLevel,
}));
vi.mock('../../../api/channelsOutcomes', async (original) => ({ ...(await original<typeof import('../../../api/channelsOutcomes')>()),
  registerConfidentialArtifact: api.registerConfidentialArtifact,
}));

import OpportunityIntelligence from '../OpportunityIntelligence';

function seedApi() {
  api.fetchOpportunityByLegacyStartup.mockResolvedValue({
    opportunity_id: 'opportunity-1', company_id: 'company-1', context_key: 'primary', decision_state: 'monitor',
    service_level: 3, legacy_startup_id: 'startup-1', current_evaluation_id: 'evaluation-1',
    current_recommendation_id: 'recommendation-1', current_ruling_id: null,
    created_at: '2026-07-15T12:00:00Z', updated_at: '2026-07-15T12:00:00Z',
  });
  api.fetchCompany.mockResolvedValue({
    company_id: 'company-1', canonical_name: 'Acme', canonical_domain: 'acme.ai', identity_confidence: 0.98,
    status: 'active', created_at: '2026-07-15T12:00:00Z', updated_at: '2026-07-15T12:00:00Z',
  });
  api.fetchObservations.mockResolvedValue([]);
  api.fetchEvidenceLedger.mockResolvedValue({
    artifacts: [{ artifact_id: 'artifact-1', artifact_type: 'interview_note', title: 'Founder interview', trust_class: 'founder', access_class: 'tenant_confidential' }],
    items: [{ evidence_item_id: 'item-1', artifact_id: 'artifact-1', item_type: 'interview_quote', display_excerpt: 'Shipped the first workflow in nine days after six customer interviews.', verification_state: 'verified', source_quality: 0.8, extraction_confidence: 0.9 }],
    claims: [{ claim_id: 'claim-1', company_id: 'company-1', opportunity_id: 'opportunity-1', claim_type: 'founder_speed', display_text: 'Built and shipped the first workflow in nine days.', assertion_class: 'founder_asserted', confidence: 0.82, material: true, status: 'current' }],
    links: [{ link_id: 'link-1', claim_id: 'claim-1', evidence_item_id: 'item-1', relationship: 'supports', support_strength: 0.8, rationale: 'Direct interview evidence.' }],
    plans: [],
  });
  api.fetchCurrentEvaluation.mockResolvedValue({
    evaluation: { evaluation_id: 'evaluation-1', model_id: 'gpt-5-nano', prompt_version: 'prompt-a', policy_version_id: 'policy-v3', rubric_version: 'rubric-v2' },
    recommendation: { recommendation_id: 'recommendation-1', decision: 'monitor', rationale: 'Customer pull is promising; retention evidence remains missing.', confidence: 0.68 },
  });
  api.listWorkflowActions.mockResolvedValue([{ workflow_action_id: 'action-1', opportunity_id: 'opportunity-1', action_type: 'draft_information_request', status: 'pending_approval', generated_content: { subject: 'Information request' }, missing_evidence: ['retention'], requires_approval: true, created_at: '2026-07-15T12:00:00Z', updated_at: '2026-07-15T12:00:00Z' }]);
  api.fetchMonitoringStatus.mockResolvedValue({ service_level: 3, recent_reservations: [] });
  api.createHumanRuling.mockResolvedValue({ ruling_id: 'ruling-1', decision: 'monitor' });
  api.approveWorkflowAction.mockResolvedValue({ status: 'approved' });
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

  it('shows observable founder signals with linked evidence, never an unsupported founder label', async () => {
    renderWorkspace();
    const founderSignals = await screen.findByLabelText('Evidence-backed founder signals');
    expect(within(founderSignals).getByText('Built and shipped the first workflow in nine days.')).toBeInTheDocument();
    expect(within(founderSignals).getByText('Shipped the first workflow in nine days after six customer interviews.')).toBeInTheDocument();
    expect(screen.queryByText(/magnetic founder/i)).not.toBeInTheDocument();
  });

  it('discloses immutable evaluation dependencies beside the recommendation', async () => {
    renderWorkspace();
    fireEvent.click(await screen.findByRole('tab', { name: 'Decision' }));
    expect(await screen.findByText('Customer pull is promising; retention evidence remains missing.')).toBeInTheDocument();
    expect(screen.getByText('gpt-5-nano')).toBeInTheDocument();
    expect(screen.getByText('policy-v3')).toBeInTheDocument();
  });

  it('requires a rationale before recording a human ruling', async () => {
    renderWorkspace();
    fireEvent.click(await screen.findByRole('tab', { name: 'Decision' }));
    fireEvent.click(screen.getByRole('button', { name: 'Monitor' }));
    expect(screen.getByRole('button', { name: 'Record ruling' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Ruling rationale'), { target: { value: 'Customer pull is credible; monitor until retention is verified.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Record ruling' }));
    await waitFor(() => expect(api.createHumanRuling).toHaveBeenCalledWith('opportunity-1', expect.objectContaining({
      decision: 'monitor', rationale: 'Customer pull is credible; monitor until retention is verified.',
    })));
  });

  it('keeps generated external actions behind explicit approval', async () => {
    renderWorkspace();
    fireEvent.click(await screen.findByRole('tab', { name: 'Actions' }));
    expect(await screen.findByText('Approval required')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Approve action' }));
    await waitFor(() => expect(api.approveWorkflowAction).toHaveBeenCalledWith('action-1', { subject: 'Information request' }));
  });
});
