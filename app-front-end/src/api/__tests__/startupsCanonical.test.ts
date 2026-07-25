import { beforeEach, describe, expect, it, vi } from 'vitest';

const { authedFetch } = vi.hoisted(() => ({ authedFetch: vi.fn() }));
vi.mock('../auth', () => ({ authedFetch }));

import { fetchStartups } from '../startups';

const response = (body: unknown, ok = true, status = 200) => ({
  ok,
  status,
  json: async () => body,
});

describe('canonical startup queue adapter', () => {
  beforeEach(() => authedFetch.mockReset());

  it('reads canonical opportunities for certified canonical-read tenants', async () => {
    authedFetch
      .mockResolvedValueOnce(response({ mode: 'canonical_read', canonical_reads_allowed: true }))
      .mockResolvedValueOnce(response({ opportunities: [{
        opportunity_id: 'opp-1', company_id: 'co-1', canonical_name: 'Acme', canonical_domain: 'acme.com',
        decision_state: 'advance', workflow_state: 'ruling_pending', recommended_state: 'advance',
        recommendation_confidence: 0.8, decision_drivers: ['market'], principal_risks: ['retention'],
      }] }));

    const startups = await fetchStartups();
    expect(startups[0].id).toBe('opp-1');
    expect(startups[0].scout.name).toBe('Acme');
    expect(startups[0].partner?.recommendation).toBe('MONITOR');
    expect(authedFetch).toHaveBeenCalledTimes(2);
    expect(authedFetch.mock.calls[1][0]).toContain('/api/opportunities');
  });

  it('keeps the legacy queue for non-canonical tenants', async () => {
    authedFetch
      .mockResolvedValueOnce(response({ mode: 'shadow', canonical_reads_allowed: false }))
      .mockResolvedValueOnce(response([{ id: 'startup-1' }]));
    await expect(fetchStartups()).resolves.toEqual([{ id: 'startup-1' }]);
  });
});
