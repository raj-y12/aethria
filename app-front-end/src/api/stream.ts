/**
 * Server-Sent Events client for GET /api/stream.
 *
 * Consumed with `fetch` (not the native EventSource) so we can:
 *   - send the Clerk JWT via the standard Authorization header (no token in the
 *     URL, which would leak into logs), and
 *   - fetch a FRESH token on every (re)connect, which matters because Clerk
 *     tokens are short-lived.
 *
 * The server pushes tiny `{ "type": "startups_changed" }` nudges; the caller
 * reacts by refetching through the normal typed REST clients. This module owns
 * connection lifecycle only: reconnect with exponential backoff + jitter, and
 * clean teardown via AbortController. If the stream can't be established the
 * caller falls back to polling, so a failure here only costs freshness.
 */
import { getAuthHeaders } from './auth';

const API_BASE =
  typeof window !== 'undefined'
    ? (import.meta.env.VITE_API_URL ?? '')
    : 'http://localhost:8000';

export type StreamEvent = { type: string; [key: string]: unknown };
export type StreamStatus = 'open' | 'closed';

export interface StreamHandle {
  /** Permanently close the stream and stop reconnecting. */
  close: () => void;
}

const BACKOFF_BASE_MS = 1_000;
const BACKOFF_MAX_MS = 30_000;

/** Exponential backoff (capped) with 50% jitter to avoid thundering herds. */
function backoffMs(attempt: number): number {
  const capped = Math.min(BACKOFF_BASE_MS * 2 ** Math.min(attempt, 5), BACKOFF_MAX_MS);
  return capped / 2 + Math.random() * (capped / 2);
}

/** Abortable sleep. Resolves early (without throwing) when the signal aborts. */
function delay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal.aborted) {
      resolve();
      return;
    }
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(timer);
      resolve();
    };
    signal.addEventListener('abort', onAbort, { once: true });
  });
}

/** Extract the joined `data:` payload from one raw SSE frame (ignores comments). */
function parseFrameData(rawFrame: string): string | null {
  const dataLines: string[] = [];
  for (const line of rawFrame.split(/\r?\n/)) {
    // Comments (keepalive / connected) start with ':' — skip them.
    if (!line || line.startsWith(':')) continue;
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).replace(/^ /, ''));
    }
  }
  return dataLines.length ? dataLines.join('\n') : null;
}

/** Read and parse SSE frames from a response body until it ends or aborts. */
async function readFrames(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: StreamEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    while (!signal.aborted) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Frames are separated by a blank line (\n\n, tolerating \r\n).
      let match = /\r?\n\r?\n/.exec(buffer);
      while (match) {
        const rawFrame = buffer.slice(0, match.index);
        buffer = buffer.slice(match.index + match[0].length);
        const data = parseFrameData(rawFrame);
        if (data) {
          try {
            const parsed = JSON.parse(data) as StreamEvent;
            if (parsed && typeof parsed.type === 'string') onEvent(parsed);
          } catch {
            // Ignore malformed payloads; the stream keeps going.
          }
        }
        match = /\r?\n\r?\n/.exec(buffer);
      }
    }
  } finally {
    try {
      await reader.cancel();
    } catch {
      /* reader already closed */
    }
  }
}

/**
 * Open the startups event stream. Returns a handle whose `close()` tears down
 * the connection and stops all reconnect attempts.
 */
export function openStartupsStream(
  onEvent: (event: StreamEvent) => void,
  onStatus?: (status: StreamStatus) => void,
): StreamHandle {
  // No backend in fixtures mode — never attempt to connect.
  if (import.meta.env.VITE_USE_FIXTURES === '1') {
    return { close: () => {} };
  }

  const controller = new AbortController();
  const { signal } = controller;
  let closed = false;
  let attempt = 0;

  const setStatus = (status: StreamStatus) => {
    if (!closed) onStatus?.(status);
  };

  async function loop(): Promise<void> {
    while (!closed) {
      try {
        // Force a fresh token on every reconnect: a long-lived stream outlives
        // the short Clerk token it opened with, so a stale one would 401 on
        // reconnect. The first attempt can use the cached token.
        const headers = await getAuthHeaders(attempt > 0, true);
        if (!headers.Authorization) {
          // Token not ready yet; back off and retry.
          await delay(backoffMs(++attempt), signal);
          continue;
        }

        const res = await fetch(`${API_BASE}/api/stream`, {
          method: 'GET',
          headers: { ...headers, Accept: 'text/event-stream' },
          signal,
        });

        if (!res.ok || !res.body) {
          // 401 (expired token), 503 (connection cap), etc. — retry with a
          // fresh token after backoff. Polling covers freshness meanwhile.
          await delay(backoffMs(++attempt), signal);
          continue;
        }

        attempt = 0; // connected — reset backoff
        setStatus('open');
        await readFrames(res.body, onEvent, signal);
        // Stream ended (server closed / network drop): mark closed, reconnect.
        setStatus('closed');
        if (!closed) await delay(backoffMs(++attempt), signal);
      } catch {
        // Aborted (teardown) or transient network error.
        if (closed || signal.aborted) break;
        setStatus('closed');
        await delay(backoffMs(++attempt), signal);
      }
    }
  }

  void loop();

  return {
    close() {
      if (closed) return;
      closed = true;
      controller.abort();
      onStatus?.('closed');
    },
  };
}
