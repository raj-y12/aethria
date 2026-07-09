/**
 * SSE health contract: an HTTP 200 alone must NOT mark the stream healthy —
 * only parsing the server's hello data frame does. A silent stream goes stale
 * after 2× the server keepalive cadence, and any later frame recovers it.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { StreamStatus } from '../src/api/stream';

vi.mock('../src/api/auth', () => ({
  getAuthHeaders: vi.fn(async () => ({ Authorization: 'Bearer test-token' })),
}));

import { openStartupsStream, streamDiagnostics } from '../src/api/stream';

function makeSseResponse() {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      controller = c;
    },
  });
  const push = (frame: string) => controller.enqueue(new TextEncoder().encode(frame));
  const res = {
    ok: true,
    status: 200,
    body,
  } as unknown as Response;
  return { res, push };
}

// Fake timers control the stale timer; a small advance also flushes the
// microtask chain that delivers stream reads.
const flush = () => vi.advanceTimersByTimeAsync(20);

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('SSE stream health', () => {
  it('is healthy only after the hello frame is parsed, and goes stale on silence', async () => {
    vi.useFakeTimers();
    const { res, push } = makeSseResponse();
    vi.stubGlobal('fetch', vi.fn(async () => res));

    const statuses: StreamStatus[] = [];
    const events: unknown[] = [];
    const handle = openStartupsStream(
      (e) => events.push(e),
      (s) => statuses.push(s),
    );

    await flush();
    // 200 received, comment frame not yet sent: connecting, never healthy.
    expect(statuses).toContain('connecting');
    expect(statuses).not.toContain('healthy');

    // A comment-only frame (`: connected`) still must not mark it healthy.
    push(': connected\n\n');
    await flush();
    expect(statuses).not.toContain('healthy');

    // The hello data frame flips it to healthy and reaches the handler.
    push('data: {"type":"startups_changed","reason":"stream_connected"}\n\n');
    await flush();
    expect(statuses).toContain('healthy');
    expect(events).toEqual([{ type: 'startups_changed', reason: 'stream_connected' }]);
    expect(streamDiagnostics.lastEventReason).toBe('stream_connected');
    expect(streamDiagnostics.lastHttpStatus).toBe(200);

    // Silence past 2× keepalive marks the stream stale…
    await vi.advanceTimersByTimeAsync(40_000);
    expect(statuses[statuses.length - 1]).toBe('stale');

    // …and a keepalive comment (proof of delivery) recovers it.
    push(': keepalive\n\n');
    await flush();
    expect(statuses[statuses.length - 1]).toBe('healthy');

    handle.close();
    expect(statuses[statuses.length - 1]).toBe('closed');
  });
});
