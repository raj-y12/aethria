import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchStartupsWithToken } from '../src/api/startups';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('login startup preload', () => {
  it('loads deal flow with the newly-created Clerk session token', async () => {
    const startups = [{ id: 's1', name: 'Acme' }];
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer fresh-token');
      return new Response(JSON.stringify(startups), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchStartupsWithToken('fresh-token')).resolves.toEqual(startups);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('degrades to null instead of holding up login', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 503 })));
    await expect(fetchStartupsWithToken('fresh-token')).resolves.toBeNull();
  });
});
