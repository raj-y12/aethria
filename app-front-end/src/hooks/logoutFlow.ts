type ActivityMarker = (options: { keepalive: boolean }) => Promise<void>;

interface LogoutDependencies {
  markActivitySeen: ActivityMarker;
  signOut?: () => Promise<void>;
  navigate: (path: string, options: { replace: boolean }) => void;
}

export async function logoutAndNavigate({ markActivitySeen, signOut, navigate }: LogoutDependencies): Promise<void> {
  localStorage.removeItem('aethria_last_activity');

  // This is useful bookkeeping, but it must never hold authentication logout
  // hostage if token refresh, the API, or Supabase is slow.
  void markActivitySeen({ keepalive: true }).catch(() => {});

  await signOut?.();
  navigate('/sign-in', { replace: true });
}
