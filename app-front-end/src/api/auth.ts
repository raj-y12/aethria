/**
 * API auth: attach Clerk JWT to requests when available.
 * setTokenGetter is called from App (under ClerkProvider) so fetch calls can add Authorization.
 */

type TokenGetter = (opts?: { skipCache?: boolean }) => Promise<string | null>;

let tokenGetter: TokenGetter | null = null;
const AUTH_TOKEN_WAIT_MS = 7500;
const AUTH_TOKEN_POLL_MS = 250;

export function setTokenGetter(getter: TokenGetter | null): void {
  tokenGetter = getter;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function getTokenWithOptionalWait(forceRefresh: boolean, waitForToken: boolean): Promise<string | null> {
  if (!tokenGetter) return null;
  const deadline = Date.now() + AUTH_TOKEN_WAIT_MS;

  while (tokenGetter) {
    const token = await tokenGetter(forceRefresh ? { skipCache: true } : undefined);
    if (token || !waitForToken || Date.now() >= deadline) return token;
    await sleep(AUTH_TOKEN_POLL_MS);
  }

  return null;
}

export async function getAuthHeaders(
  forceRefresh = false,
  waitForToken = false,
): Promise<Record<string, string>> {
  const token = await getTokenWithOptionalWait(forceRefresh, waitForToken);
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

function mergeHeaders(initHeaders: HeadersInit | undefined, authHeaders: Record<string, string>): Headers {
  const headers = new Headers(initHeaders);
  for (const [key, value] of Object.entries(authHeaders)) {
    headers.set(key, value);
  }
  return headers;
}

/**
 * Auth-aware fetch with one-time retry on 401 using a force-refreshed token.
 * This smooths over token expiry boundaries during high-frequency polling.
 */
export async function authedFetch(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Response> {
  const firstAuthHeaders = await getAuthHeaders(false, true);
  if (!firstAuthHeaders.Authorization) {
    return new Response(JSON.stringify({ detail: 'Missing authorization token' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }
  const firstHeaders = mergeHeaders(init?.headers, firstAuthHeaders);
  const first = await fetch(input, { ...init, headers: firstHeaders });
  if (first.status !== 401) return first;

  const retryAuthHeaders = await getAuthHeaders(true, true);
  if (!retryAuthHeaders.Authorization) return first;
  const retryHeaders = mergeHeaders(init?.headers, retryAuthHeaders);
  return fetch(input, { ...init, headers: retryHeaders });
}
