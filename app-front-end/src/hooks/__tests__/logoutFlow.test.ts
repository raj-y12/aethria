import { afterEach, describe, expect, it, vi } from 'vitest';
import { logoutAndNavigate } from '../logoutFlow';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('logoutAndNavigate', () => {
  it('does not block sign-out on the activity marker', async () => {
    let resolveMarker: (() => void) | undefined;
    const marker = new Promise<void>((resolve) => {
      resolveMarker = resolve;
    });
    const markActivitySeen = vi.fn(() => marker);
    const signOut = vi.fn().mockResolvedValue(undefined);
    const navigate = vi.fn();

    const logout = logoutAndNavigate({ markActivitySeen, signOut, navigate });

    await logout;

    expect(markActivitySeen).toHaveBeenCalledWith({ keepalive: true });
    expect(signOut).toHaveBeenCalledOnce();
    expect(navigate).toHaveBeenCalledWith('/sign-in', { replace: true });

    resolveMarker?.();
  });
});
