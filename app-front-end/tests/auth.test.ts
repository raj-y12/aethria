import { describe, it } from 'vitest';
import assert from 'node:assert/strict';
import { authedFetch, setTokenGetter } from '../src/api/auth.ts';

describe('authedFetch', () => {
  it('waits for the token getter to be ready, then sends the bearer token once', async () => {
    const originalFetch = globalThis.fetch;
    let fetchCalls = 0;
    let getterCalls = 0;

    globalThis.fetch = (async (_input: RequestInfo | URL, init?: RequestInit) => {
      fetchCalls += 1;
      const headers = new Headers(init?.headers);
      assert.equal(headers.get('Authorization'), 'Bearer ready-token');
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }) as typeof fetch;

    setTokenGetter(async () => {
      getterCalls += 1;
      return getterCalls < 3 ? null : 'ready-token';
    });

    try {
      const res = await authedFetch('http://localhost:8000/api/agents/status', {
        headers: { Accept: 'application/json' },
      });

      assert.equal(res.status, 200);
      assert.equal(fetchCalls, 1);
      assert.equal(getterCalls, 3);
    } finally {
      setTokenGetter(null);
      globalThis.fetch = originalFetch;
    }
  });
});
