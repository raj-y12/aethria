import { afterEach, describe, expect, it, vi } from 'vitest';
import { logoutAndNavigate } from '../logoutFlow';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('logoutAndNavigate', () => {
  it('clears confidential browser snapshots before navigating away', async () => {
    localStorage.setItem('aethria:warm:v1:user-a', '{}');
    localStorage.setItem('aethria.dispatch.lookups.v2:user-a', '{}');
    localStorage.setItem('aethria.settings.policy-publish.v1:user-a:fund', '{}');
    localStorage.setItem('aethria_fund_configuration_v1', '{}');
    localStorage.setItem('aethria_fund_configuration_v1:user-a', '{}');

    await logoutAndNavigate({
      markActivitySeen: vi.fn().mockResolvedValue(undefined),
      signOut: vi.fn().mockResolvedValue(undefined),
      navigate: vi.fn(),
    });

    expect(localStorage.getItem('aethria:warm:v1:user-a')).toBeNull();
    expect(localStorage.getItem('aethria.dispatch.lookups.v2:user-a')).toBeNull();
    expect(localStorage.getItem('aethria.settings.policy-publish.v1:user-a:fund')).toBeNull();
    expect(localStorage.getItem('aethria_fund_configuration_v1')).toBeNull();
    expect(localStorage.getItem('aethria_fund_configuration_v1:user-a')).toBeNull();
  });

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
