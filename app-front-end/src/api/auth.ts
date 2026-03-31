/**
 * API auth: attach Clerk JWT to requests when available.
 * setTokenGetter is called from App (under ClerkProvider) so fetch calls can add Authorization.
 */

type TokenGetter = (opts?: { skipCache?: boolean }) => Promise<string | null>;

let tokenGetter: TokenGetter | null = null;

export function setTokenGetter(getter: TokenGetter | null): void {
  tokenGetter = getter;
}

export async function getAuthHeaders(forceRefresh = false): Promise<Record<string, string>> {
  if (!tokenGetter) return {};
  const token = await tokenGetter(forceRefresh ? { skipCache: true } : undefined);
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

/**
 * Auth-aware fetch with one-time retry on 401 using a force-refreshed token.
 * This smooths over token expiry boundaries during high-frequency polling.
 */
export async function authedFetch(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Response> {
  const firstHeaders = {
    ...(init?.headers ?? {}),
    ...(await getAuthHeaders(false)),
  };
  const first = await fetch(input, { ...init, headers: firstHeaders });
  if (first.status !== 401) return first;

  const retryHeaders = {
    ...(init?.headers ?? {}),
    ...(await getAuthHeaders(true)),
  };
  return fetch(input, { ...init, headers: retryHeaders });
}
