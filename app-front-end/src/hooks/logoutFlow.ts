type ActivityMarker = (options: { keepalive: boolean }) => Promise<void>;

interface LogoutDependencies {
  markActivitySeen: ActivityMarker;
  signOut?: () => Promise<void>;
  navigate: (path: string, options: { replace: boolean }) => void;
}

export async function logoutAndNavigate({ markActivitySeen, signOut, navigate }: LogoutDependencies): Promise<void> {
  try {
    for (let index = localStorage.length - 1; index >= 0; index -= 1) {
      const key = localStorage.key(index);
      if (
        key?.startsWith('aethria:warm:v') ||
        key?.startsWith('aethria.dispatch.lookups.v') ||
        key?.startsWith('aethria.settings.policy-publish.v') ||
        key?.startsWith('aethria_fund_configuration_v1') ||
        key === 'aethria_last_activity'
      ) {
        localStorage.removeItem(key);
      }
    }
  } catch {
    // Sign-out must still complete if browser storage is unavailable.
  }

  // This is useful bookkeeping, but it must never hold authentication logout
  // hostage if token refresh, the API, or Supabase is slow.
  void markActivitySeen({ keepalive: true }).catch(() => {});

  await signOut?.();
  navigate('/sign-in', { replace: true });
}
