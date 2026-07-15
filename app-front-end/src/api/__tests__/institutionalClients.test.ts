import { beforeEach, describe, expect, it, vi } from 'vitest';

const { authedFetch } = vi.hoisted(() => ({ authedFetch: vi.fn() }));

vi.mock('../auth', () => ({ authedFetch }));

import { fetchJob, retryJob } from '../jobs';
import { fetchIdentityCases, resolveIdentityCase } from '../identity';
import { correctClaim, fetchEvidenceLedger } from '../evidence';
import { createHumanRuling, listWorkflowActions } from '../decisions';
import { requestEvidenceRefresh } from '../monitoring';
import { reviewPolicyProposal } from '../fundIntelligence';
import { createOutcome, importCsv } from '../channelsOutcomes';

describe('institutional API clients', () => {
  beforeEach(() => authedFetch.mockReset());

  it('preserves exact durable job states and retries the same job', async () => {
    authedFetch
      .mockResolvedValueOnce(new Response(JSON.stringify({
        job_id: 'job-12345678',
        job_type: 'company_lookup',
        status: 'retry_wait',
        attempts: 1,
        max_attempts: 3,
        pipeline_run_id: 'run-1',
        lookup_id: 'lookup-12345678',
        accepted_at: '2026-07-15T12:00:00Z',
        next_attempt_at: '2026-07-15T12:01:00Z',
        block_code: null,
        recovery_action: null,
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        job_id: 'job-12345678',
        job_type: 'company_lookup',
        status: 'accepted',
        attempts: 1,
        max_attempts: 3,
        pipeline_run_id: 'run-1',
        lookup_id: 'lookup-12345678',
        accepted_at: '2026-07-15T12:00:00Z',
        next_attempt_at: '2026-07-15T12:01:00Z',
      }), { status: 202 }));

    await expect(fetchJob('job-12345678')).resolves.toMatchObject({ status: 'retry_wait' });
    await retryJob('job-12345678');

    expect(authedFetch).toHaveBeenLastCalledWith(
      expect.stringContaining('/api/jobs/job-12345678/retry'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('lists and resolves identity cases without client-supplied tenant fields', async () => {
    authedFetch
      .mockResolvedValueOnce(new Response(JSON.stringify({ cases: [] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        observation_id: 'observation-1', status: 'resolved', company_id: 'company-1',
        opportunity_id: 'opportunity-1', blocks_evaluation: false, created: false,
      }), { status: 200 }));

    await fetchIdentityCases('open');
    await resolveIdentityCase('case-12345678', {
      action: 'match',
      selected_company_id: 'company-1',
      resolution_note: 'Confirmed against official domain.',
    });

    const request = authedFetch.mock.calls[1][1] as RequestInit;
    expect(JSON.parse(String(request.body))).toEqual({
      action: 'match',
      selected_company_id: 'company-1',
      resolution_note: 'Confirmed against official domain.',
    });
  });

  it('reads the evidence ledger and sends an explicit claim correction', async () => {
    authedFetch
      .mockResolvedValueOnce(new Response(JSON.stringify({ artifacts: [], claims: [], links: [], plans: [] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ claim_id: 'claim-1', status: 'withdrawn' }), { status: 200 }));

    await fetchEvidenceLedger('opportunity-1');
    await correctClaim('claim-1', { action: 'withdraw', rationale: 'Founder corrected this statement.' });

    expect(authedFetch).toHaveBeenLastCalledWith(
      expect.stringContaining('/api/claims/claim-1/correct'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('creates human rulings and reads approval-gated actions', async () => {
    authedFetch
      .mockResolvedValueOnce(new Response(JSON.stringify({ ruling_id: 'ruling-1', decision: 'invest' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ actions: [] }), { status: 200 }));

    await createHumanRuling('opportunity-1', {
      decision: 'invest', rationale: 'Customer evidence clears the core risk.', investor_confidence: 0.8,
    });
    await listWorkflowActions('opportunity-1');

    expect(authedFetch.mock.calls[0][0]).toContain('/api/opportunities/opportunity-1/rulings');
    expect(authedFetch.mock.calls[1][0]).toContain('/api/opportunities/opportunity-1/actions');
  });

  it('returns the refresh budget reservation with its durable job', async () => {
    authedFetch.mockResolvedValueOnce(new Response(JSON.stringify({
      status: 'accepted', job_id: 'job-refresh-1', pipeline_run_id: 'run-refresh-1',
      accepted_at: '2026-07-15T12:00:00Z', budget_reservation: { amount_usd: 0.24 },
    }), { status: 202 }));

    const result = await requestEvidenceRefresh('opportunity-1', {
      reason: 'human_request', request_key: 'refresh-12345678', envelope: {},
    });

    expect(result.budget_reservation).toEqual({ amount_usd: 0.24 });
  });

  it('reviews proposals and imports channel data with explicit idempotency', async () => {
    authedFetch
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: 'approved' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ import_batch_id: 'batch-1', status: 'completed' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ outcome_id: 'outcome-1' }), { status: 200 }));

    await reviewPolicyProposal('proposal-1', { action: 'accept', rationale: 'Validated on the preview cohort.' });
    await importCsv({ idempotency_key: 'import-12345678', csv_text: 'company_name,website\nAcme,acme.test' });
    await createOutcome('company-1', {
      outcome_type: 'financing', valence: 'positive', summary: 'Closed the seed round.', materiality: 4,
    });

    const importRequest = authedFetch.mock.calls[1][1] as RequestInit;
    expect(JSON.parse(String(importRequest.body))).toMatchObject({ idempotency_key: 'import-12345678' });
  });
});
