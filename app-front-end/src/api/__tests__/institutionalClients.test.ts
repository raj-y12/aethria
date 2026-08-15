import { beforeEach, describe, expect, it, vi } from 'vitest';

const { authedFetch } = vi.hoisted(() => ({ authedFetch: vi.fn() }));

vi.mock('../auth', () => ({ authedFetch }));

import { fetchJob, retryJob } from '../jobs';
import { fetchIdentityCases, resolveIdentityCase } from '../identity';
import { correctClaim, fetchEvidenceLedger } from '../evidence';
import { createHumanRuling, createInvestmentTransition, listHumanRulings } from '../decisions';
import { fetchCurrentEvaluation } from '../evaluations';
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
      .mockResolvedValueOnce(new Response(JSON.stringify({
        artifacts: [], evidence_items: [], claims: [],
        claim_evidence_links: [{ link_id: 'link-1', claim_id: 'claim-1', evidence_item_id: 'item-1', relationship: 'supports', support_strength: 0.8, rationale: 'Direct evidence.' }],
        evidence_plans: [{ evidence_plan_id: 'plan-1', opportunity_id: 'opportunity-1', trigger_type: 'human_request', status: 'planned', missing_evidence: [], search_questions: [], max_artifacts: 5, budget_usd: 0, created_at: '2026-07-15T12:00:00Z' }],
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ claim_id: 'claim-1', status: 'withdrawn' }), { status: 200 }));

    await expect(fetchEvidenceLedger('opportunity-1')).resolves.toMatchObject({
      links: [{ link_id: 'link-1' }],
      plans: [{ evidence_plan_id: 'plan-1' }],
    });
    await correctClaim('claim-1', { action: 'withdraw', rationale: 'Founder corrected this statement.' });

    expect(authedFetch).toHaveBeenLastCalledWith(
      expect.stringContaining('/api/claims/claim-1/correct'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('normalizes stringified evaluation JSON from an older backend during rollout', async () => {
    authedFetch.mockResolvedValueOnce(new Response(JSON.stringify({
      evaluation: {
        evaluation_id: 'evaluation-1',
        model_manifest: '{"model_id":"gpt-5-nano"}',
        prompt_manifest: '{"prompt_version":"prompt-a"}',
      },
      criteria: [{ criterion: 'market', missing_evidence: '["retention"]' }],
      recommendation: {
        recommendation_id: 'recommendation-1',
        recommended_state: 'insufficient_evidence',
        decision_drivers: '[]',
        principal_risks: '["Retention is unverified."]',
        mandate_conflicts: '[]',
        missing_information: '["Net retention"]',
        change_conditions: '["Verify three-month retention."]',
      },
    }), { status: 200 }));

    const result = await fetchCurrentEvaluation('opportunity-1');

    expect(result.evaluation.model_manifest).toEqual({ model_id: 'gpt-5-nano' });
    expect(result.criteria[0].missing_evidence).toEqual(['retention']);
    expect(result.recommendation?.decision_drivers).toEqual([]);
    expect(result.recommendation?.principal_risks).toEqual(['Retention is unverified.']);
    expect(result.recommendation?.change_conditions).toEqual(['Verify three-month retention.']);
  });

  it('normalizes criterion claim and quality arrays across rollout payload shapes', async () => {
    authedFetch.mockResolvedValueOnce(new Response(JSON.stringify({
      evaluation: { evaluation_id: 'evaluation-1', model_manifest: {}, prompt_manifest: {} },
      criteria: [
        {
          criterion: 'stringified',
          supporting_claim_ids: '["claim-support"]',
          contradicting_claim_ids: '["claim-contradiction"]',
          quality_flags: '["weak_sources"]',
        },
        {
          criterion: 'malformed',
          supporting_claim_ids: '[not json', contradicting_claim_ids: '{}', quality_flags: 'not json',
        },
        { criterion: 'missing' },
        {
          criterion: 'arrays',
          supporting_claim_ids: ['claim-a'], contradicting_claim_ids: ['claim-b'], quality_flags: ['contested_review'],
        },
      ],
      recommendation: null,
    }), { status: 200 }));

    const result = await fetchCurrentEvaluation('opportunity-1');

    expect(result.criteria.map((criterion) => ({
      criterion: criterion.criterion,
      supporting: criterion.supporting_claim_ids,
      contradicting: criterion.contradicting_claim_ids,
      flags: criterion.quality_flags,
    }))).toEqual([
      { criterion: 'stringified', supporting: ['claim-support'], contradicting: ['claim-contradiction'], flags: ['weak_sources'] },
      { criterion: 'malformed', supporting: [], contradicting: [], flags: [] },
      { criterion: 'missing', supporting: [], contradicting: [], flags: [] },
      { criterion: 'arrays', supporting: ['claim-a'], contradicting: ['claim-b'], flags: ['contested_review'] },
    ]);
  });

  it('creates human rulings and reads their history', async () => {
    authedFetch
      .mockResolvedValueOnce(new Response(JSON.stringify({ ruling_id: 'ruling-1', decision: 'advance' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ rulings: [{ ruling_id: 'ruling-1', decision: 'invest' }] }), { status: 200 }));

    await createHumanRuling('opportunity-1', {
      decision: 'advance', rationale: 'Customer evidence clears the core risk.',
    });
    await expect(listHumanRulings('opportunity-1')).resolves.toMatchObject([{ ruling_id: 'ruling-1' }]);

    expect(authedFetch.mock.calls[0][0]).toContain('/api/opportunities/opportunity-1/rulings');
    expect(authedFetch.mock.calls[1][0]).toContain('/api/opportunities/opportunity-1/rulings?limit=');
  });

  it('records a post-diligence investment transition separately from a ruling', async () => {
    authedFetch.mockResolvedValueOnce(new Response(JSON.stringify({
      decision: 'invest', position: { position_id: 'position-1' }, idempotent: false,
    }), { status: 200 }));

    await expect(createInvestmentTransition('opportunity-1', {
      rationale: 'Diligence is complete and the committee approved the allocation.',
      investor_confidence: 0.86,
    })).resolves.toMatchObject({ decision: 'invest', idempotent: false });
    expect(authedFetch.mock.calls[0][0]).toContain('/api/opportunities/opportunity-1/investment');
    expect(JSON.parse(authedFetch.mock.calls[0][1].body)).toEqual({
      rationale: 'Diligence is complete and the committee approved the allocation.',
      investor_confidence: 0.86,
    });
  });

  it('reviews proposals and imports channel data with explicit idempotency', async () => {
    authedFetch
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: 'approved' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ import_batch_id: 'batch-1', status: 'completed' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ outcome_id: 'outcome-1' }), { status: 200 }));

    await reviewPolicyProposal('proposal-1', {
      action: 'edit_and_accept', rationale: 'Validated on the preview cohort.',
      edited_policy_patch: { scoringWeights: [] },
    });
    await importCsv({ idempotency_key: 'import-12345678', csv_text: 'company_name,website\nAcme,acme.test' });
    await createOutcome('company-1', {
      outcome_type: 'financing', valence: 'positive', summary: 'Closed the seed round.', materiality: 4,
    });

    const importRequest = authedFetch.mock.calls[1][1] as RequestInit;
    expect(JSON.parse(String(importRequest.body))).toMatchObject({ idempotency_key: 'import-12345678' });
  });
});
