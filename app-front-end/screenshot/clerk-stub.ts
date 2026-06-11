/**
 * Clerk stub for the screenshot harness — vite.screenshot.config.ts aliases
 * '@clerk/react-router' and '@clerk/react' here so the real pages render
 * without an auth backend.
 */

export function useAuth() {
  return {
    userId: 'user_demo',
    isLoaded: true,
    isSignedIn: true,
    getToken: async () => 'demo-token',
  };
}

export function useClerk() {
  return { signOut: async () => {} };
}

export function useUser() {
  return {
    isLoaded: true,
    user: {
      username: 'a-raj',
      fullName: 'A. Raj',
      primaryEmailAddress: { emailAddress: 'raj@aethria.com' },
    },
  };
}

export function ClerkProvider({ children }: { children: React.ReactNode }) {
  return children;
}
