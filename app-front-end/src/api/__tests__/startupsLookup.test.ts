import { beforeEach, describe, expect, it, vi } from 'vitest';

const { authedFetch } = vi.hoisted(() => ({
  authedFetch: vi.fn(),
}));

vi.mock('../auth', () => ({ authedFetch }));

import {
  fetchLookupJobStatus,
  isLookupTerminalStatus,
  queueOnDemandLookup,
  resolveLookupCandidates,
} from '../startups';

describe('lookup resolution handoff', () => {
  beforeEach(() => {
    authedFetch.mockReset();
  });

  it('returns the opaque resolution token and sends it with the queued lookup', async () => {
    authedFetch
      .mockResolvedValueOnce(new Response(JSON.stringify({
        status: 'resolved',
        canonical_name: 'Acme',
        company_name: 'Acme',
        website_hint: null,
        resolution_token: 'resolution-token-123',
        candidates: [{
          name: 'Acme',
          website: 'https://acme.example',
          description: 'Robotics',
          confidence: 0.95,
          source_badges: ['official'],
        }],
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        status: 'accepted',
        company_name: 'Acme',
        lookup_id: 'lookup-acme-123',
        job_id: 'job-acme-123',
        accepted_at: '2026-07-15T12:00:00Z',
        pipeline_run_id: 'run-acme-123',
      }), { status: 202 }));

    const resolved = await resolveLookupCandidates('Acme');
    const queued = await queueOnDemandLookup(
      'Acme https://acme.example',
      'lookup-acme-123',
      undefined,
      resolved.resolutionToken,
    );

    expect(resolved.resolutionToken).toBe('resolution-token-123');
    expect(queued).toMatchObject({
      status: 'accepted',
      jobId: 'job-acme-123',
      acceptedAt: '2026-07-15T12:00:00Z',
      pipelineRunId: 'run-acme-123',
    });
    const request = authedFetch.mock.calls[1][1] as RequestInit;
    expect(JSON.parse(String(request.body))).toMatchObject({
      resolution_token: 'resolution-token-123',
    });
  });
});

describe('lookup execution status contract', () => {
  beforeEach(() => {
    authedFetch.mockReset();
  });

  it.each([
    ['pending', false, false],
    ['accepted', false, false],
    ['completed', true, false],
    ['blocked', true, true],
    ['skipped', true, false],
    ['failed_stage', true, true],
    ['failed', true, true],
    ['already_in_deal_flow', true, false],
  ] as const)(
    'preserves %s instead of coercing it to pending',
    async (status, terminal, failed) => {
      authedFetch.mockResolvedValueOnce(new Response(JSON.stringify({
        lookup_id: 'lookup-status-1',
        status,
        terminal,
        failed,
      }), { status: 200 }));

      const result = await fetchLookupJobStatus('lookup-status-1');

      expect(result.status).toBe(status);
      expect(result.terminal).toBe(terminal);
      expect(result.failed).toBe(failed);
      expect(isLookupTerminalStatus(result.status)).toBe(terminal);
    },
  );

  it('preserves actionable blocked and failed-stage metadata', async () => {
    authedFetch.mockResolvedValueOnce(new Response(JSON.stringify({
      lookup_id: 'lookup-status-2',
      status: 'failed_stage',
      terminal: true,
      failed: true,
      code: 'reviewer_stage_failed',
      failed_stage: 'reviewer',
      detail: 'Reviewer could not complete.',
      recovery_action: 'Inspect Reviewer logs and retry.',
    }), { status: 200 }));

    await expect(fetchLookupJobStatus('lookup-status-2')).resolves.toMatchObject({
      status: 'failed_stage',
      terminal: true,
      failed: true,
      code: 'reviewer_stage_failed',
      failed_stage: 'reviewer',
      detail: 'Reviewer could not complete.',
      recovery_action: 'Inspect Reviewer logs and retry.',
    });
  });

  it('fails closed on an unknown persisted status', async () => {
    authedFetch.mockResolvedValueOnce(new Response(JSON.stringify({
      lookup_id: 'lookup-status-3',
      status: 'mystery_state',
    }), { status: 200 }));

    await expect(fetchLookupJobStatus('lookup-status-3')).resolves.toMatchObject({
      status: 'failed',
      terminal: true,
      failed: true,
      code: 'lookup_status_invalid',
    });
  });
});
