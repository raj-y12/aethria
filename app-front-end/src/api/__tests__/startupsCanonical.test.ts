import { beforeEach, describe, expect, it, vi } from 'vitest';

const { authedFetch } = vi.hoisted(() => ({ authedFetch: vi.fn() }));
vi.mock('../auth', () => ({ authedFetch }));

import { fetchStartups, fetchStartupDetail } from '../startups';

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
    expect(startups[0].canonical_opportunity_id).toBe('opp-1');
    expect(startups[0].scout.name).toBe('Acme');
    expect(startups[0].partner?.recommendation).toBe('MONITOR');
    expect(authedFetch).toHaveBeenCalledTimes(2);
    expect(authedFetch.mock.calls[1][0]).toContain('/api/opportunities');
  });

  it('preserves the canonical opportunity id when the queue row has a legacy id', async () => {
    authedFetch
      .mockResolvedValueOnce(response({ mode: 'canonical_read', canonical_reads_allowed: true }))
      .mockResolvedValueOnce(response({ opportunities: [{
        opportunity_id: 'opp-legacy-linked', company_id: 'co-1', legacy_startup_id: 'startup-1',
        canonical_name: 'Acme', canonical_domain: 'acme.com', recommended_state: 'pass',
      }] }));

    const startups = await fetchStartups();

    expect(startups[0].id).toBe('startup-1');
    expect(startups[0].canonical_opportunity_id).toBe('opp-legacy-linked');
    expect(startups[0].partner?.recommendation).toBe('PASS');
  });

  it('projects a canonical pass ruling into the legacy portfolio bucket', async () => {
    authedFetch
      .mockResolvedValueOnce(response({ mode: 'canonical_read', canonical_reads_allowed: true }))
      .mockResolvedValueOnce(response({ opportunities: [{
        opportunity_id: 'opp-passed', company_id: 'co-1', legacy_startup_id: 'startup-passed',
        canonical_name: 'Passed Co', recommended_state: 'advance', decision_state: 'pass',
        updated_at: '2026-07-28T10:00:00Z',
      }] }));

    const startups = await fetchStartups();

    expect(startups[0].human_resolution).toEqual({
      decision: 'NO',
      resolved_at: '2026-07-28T10:00:00Z',
    });
  });

  it('uses the authoritative current ruling when the opportunity summary is stale', async () => {
    authedFetch
      .mockResolvedValueOnce(response({ mode: 'canonical_read', canonical_reads_allowed: true }))
      .mockResolvedValueOnce(response({ opportunities: [{
        opportunity_id: 'opp-passed-stale-summary', company_id: 'co-1', legacy_startup_id: 'startup-passed-stale',
        canonical_name: 'Passed Co', recommended_state: 'advance', decision_state: 'completed',
        current_ruling_decision: 'pass', updated_at: '2026-07-28T10:00:00Z',
      }] }));

    const startups = await fetchStartups();

    expect(startups[0].human_resolution?.decision).toBe('NO');
  });

  it('resolves a legacy queue id before reading its canonical decision view', async () => {
    authedFetch
      .mockResolvedValueOnce(response({ mode: 'canonical_read', canonical_reads_allowed: true }))
      .mockResolvedValueOnce(response({}, false, 404))
      .mockResolvedValueOnce(response({ opportunity_id: 'opp-legacy-linked' }))
      .mockResolvedValueOnce(response({
        opportunity_id: 'opp-legacy-linked', company_id: 'co-1', legacy_startup_id: 'startup-1',
        canonical_name: 'Acme', recommended_state: 'advance',
      }));

    const startup = await fetchStartupDetail('startup-1');

    expect(startup?.canonical_opportunity_id).toBe('opp-legacy-linked');
    expect(startup?.partner?.recommendation).toBe('MONITOR');
    expect(authedFetch.mock.calls[3][0]).toContain('/api/opportunities/opp-legacy-linked/decision-view');
  });

  it('keeps the legacy queue for non-canonical tenants', async () => {
    authedFetch
      .mockResolvedValueOnce(response({ mode: 'shadow', canonical_reads_allowed: false }))
      .mockResolvedValueOnce(response([{ id: 'startup-1' }]));
    await expect(fetchStartups()).resolves.toEqual([{ id: 'startup-1' }]);
  });
});
