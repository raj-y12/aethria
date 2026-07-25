import { beforeEach, describe, expect, it, vi } from 'vitest';

const { authedFetch } = vi.hoisted(() => ({ authedFetch: vi.fn() }));

vi.mock('./auth', () => ({ authedFetch }));

import {
  getAuthorityStatus,
  rollbackAuthority,
  transitionAuthority,
} from './authority';

const status = {
  mode: 'canonical_read' as const,
  version: 4,
  kill_switch: false,
  canonical_writes_allowed: false,
  canonical_reads_allowed: true,
  last_reconciliation_status: 'green',
};

describe('authority API client', () => {
  beforeEach(() => authedFetch.mockReset());

  it('reads the authenticated tenant authority status', async () => {
    authedFetch.mockResolvedValueOnce(new Response(JSON.stringify(status), { status: 200 }));

    await expect(getAuthorityStatus()).resolves.toEqual(status);

    expect(authedFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/authority/status'),
      expect.objectContaining({ headers: expect.objectContaining({ Accept: 'application/json' }) }),
    );
  });

  it('cannot transition authority without an expected version', async () => {
    await expect(
      transitionAuthority({ target_mode: 'shadow' } as never),
    ).rejects.toThrow('expected_version is required');

    expect(authedFetch).not.toHaveBeenCalled();
  });

  it('sends rollback with the optimistic-lock version and operator reason', async () => {
    const rolledBack = { ...status, mode: 'legacy' as const, version: 5, kill_switch: true };
    authedFetch.mockResolvedValueOnce(new Response(JSON.stringify(rolledBack), { status: 200 }));

    await expect(rollbackAuthority({
      expected_version: 4,
      reason: 'Reconciliation mismatch',
    })).resolves.toEqual(rolledBack);

    expect(authedFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/authority/rollback'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ expected_version: 4, reason: 'Reconciliation mismatch' }),
      }),
    );
  });
});
