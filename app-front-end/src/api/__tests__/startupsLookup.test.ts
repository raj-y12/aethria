import { beforeEach, describe, expect, it, vi } from 'vitest';

const { authedFetch } = vi.hoisted(() => ({
  authedFetch: vi.fn(),
}));

vi.mock('../auth', () => ({ authedFetch }));

import { queueOnDemandLookup, resolveLookupCandidates } from '../startups';

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
