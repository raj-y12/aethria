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
 *
 * Health model: an HTTP 200 alone does NOT make the stream healthy — a proxy
 * can hold a 200 open while buffering frames. The stream is `healthy` only
 * after the server's hello frame (the first `data:` event) is actually parsed,
 * proving end-to-end delivery. If no frame (including keepalive comments)
 * arrives within 2× the server keepalive cadence, the stream is `stale` and
 * callers should fall back to brisk polling.
 */
import { getAuthHeaders } from './auth';

const API_BASE =
  typeof window !== 'undefined'
    ? (import.meta.env.VITE_API_URL ?? '')
    : 'http://localhost:8000';

export type StreamEvent = { type: string; [key: string]: unknown };
export type StreamStatus = 'connecting' | 'healthy' | 'stale' | 'closed';

export interface StreamHandle {
  /** Permanently close the stream and stop reconnecting. */
  close: () => void;
}

/** Connection diagnostics, updated in place. Read for debugging/telemetry. */
export interface StreamDiagnostics {
  connectedAt: number | null;
  lastEventAt: number | null;
  reconnectCount: number;
  lastHttpStatus: number | null;
  lastEventReason: string | null;
}

export const streamDiagnostics: StreamDiagnostics = {
  connectedAt: null,
  lastEventAt: null,
  reconnectCount: 0,
  lastHttpStatus: null,
  lastEventReason: null,
};

const BACKOFF_BASE_MS = 1_000;
const BACKOFF_MAX_MS = 30_000;
// Server emits `: keepalive` every SSE_KEEPALIVE_SECONDS (20s default). If no
// frame at all lands within 2× that, delivery is broken even if the HTTP
// connection looks open.
const STALE_AFTER_MS = 40_000;

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

/**
 * Read and parse SSE frames from a response body until it ends or aborts.
 * `onFrame` fires for EVERY completed frame — including comment-only keepalives
 * — so the caller can track delivery liveness, not just data events.
 */
export async function readFrames(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: StreamEvent) => void,
  signal: AbortSignal,
  onFrame?: () => void,
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
        onFrame?.();
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
  let staleTimer: ReturnType<typeof setTimeout> | null = null;

  const setStatus = (status: StreamStatus) => {
    if (!closed) onStatus?.(status);
  };

  const clearStaleTimer = () => {
    if (staleTimer) {
      clearTimeout(staleTimer);
      staleTimer = null;
    }
  };

  async function loop(): Promise<void> {
    while (!closed) {
      let sawHello = false;
      try {
        setStatus('connecting');
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
        streamDiagnostics.lastHttpStatus = res.status;

        if (!res.ok || !res.body) {
          // 401 (expired token), 503 (connection cap), etc. — retry with a
          // fresh token after backoff. Polling covers freshness meanwhile.
          streamDiagnostics.reconnectCount += 1;
          await delay(backoffMs(++attempt), signal);
          continue;
        }

        attempt = 0; // connected — reset backoff
        streamDiagnostics.connectedAt = Date.now();
        // NOT healthy yet: a 200 only proves the request reached something
        // that speaks HTTP. Health requires the hello frame to be parsed.
        const onFrame = () => {
          clearStaleTimer();
          staleTimer = setTimeout(() => setStatus('stale'), STALE_AFTER_MS);
          // Any parsed frame after hello (data or keepalive comment) proves
          // delivery, so it also recovers a stale stream.
          if (sawHello) setStatus('healthy');
        };
        onFrame(); // arm staleness from connect; hello must arrive promptly
        await readFrames(
          res.body,
          (event) => {
            streamDiagnostics.lastEventAt = Date.now();
            streamDiagnostics.lastEventReason =
              typeof event.reason === 'string' ? event.reason : null;
            if (!sawHello) {
              sawHello = true;
              setStatus('healthy');
            }
            onEvent(event);
          },
          signal,
          onFrame,
        );
        // Stream ended (server closed / network drop): mark closed, reconnect.
        clearStaleTimer();
        setStatus('closed');
        if (!closed) {
          streamDiagnostics.reconnectCount += 1;
          await delay(backoffMs(++attempt), signal);
        }
      } catch (err) {
        // Aborted (teardown) or transient network error.
        clearStaleTimer();
        if (closed || signal.aborted) break;
        console.debug('[stream] connection error, will reconnect:', err);
        streamDiagnostics.reconnectCount += 1;
        setStatus('closed');
        await delay(backoffMs(++attempt), signal);
      }
    }
    clearStaleTimer();
  }

  void loop();

  return {
    close() {
      if (closed) return;
      closed = true;
      controller.abort();
      clearStaleTimer();
      onStatus?.('closed');
    },
  };
}
