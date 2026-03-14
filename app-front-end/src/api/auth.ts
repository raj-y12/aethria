/**
 * API auth: attach Clerk JWT to requests when available.
 * setTokenGetter is called from App (under ClerkProvider) so fetch calls can add Authorization.
 */

let tokenGetter: (() => Promise<string | null>) | null = null;

export function setTokenGetter(getter: (() => Promise<string | null>) | null): void {
  tokenGetter = getter;
}

export async function getAuthHeaders(): Promise<Record<string, string>> {
  if (!tokenGetter) return {};
  const token = await tokenGetter();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}
