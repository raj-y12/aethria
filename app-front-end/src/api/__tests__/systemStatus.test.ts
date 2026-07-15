import { beforeEach, describe, expect, it, vi } from 'vitest';

const { authedFetch } = vi.hoisted(() => ({ authedFetch: vi.fn() }));
vi.mock('../auth', () => ({ authedFetch }));

import { fetchSystemStatus } from '../system';

describe('system status client', () => {
  beforeEach(() => authedFetch.mockReset());

  it('reads authenticated durable execution readiness and exact queue states', async () => {
    authedFetch.mockResolvedValue(new Response(JSON.stringify({
      status: 'ok',
      durable_jobs: {
        required: true,
        ready: true,
        error: null,
        counts: { 'pipeline_cycle:queued': 2, 'company_lookup:retry_wait': 3, 'outbox:pending': 4 },
      },
    }), { status: 200 }));

    await expect(fetchSystemStatus()).resolves.toMatchObject({
      durable_jobs: { ready: true, counts: { 'company_lookup:retry_wait': 3 } },
    });
    expect(authedFetch).toHaveBeenCalledWith(expect.stringContaining('/api/system/status'), expect.any(Object));
  });
});
