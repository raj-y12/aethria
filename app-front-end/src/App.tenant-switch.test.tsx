import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { useEffect, type ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Regression coverage for "Switching operator accounts can display another
// tenant's local UI state" (docs/known-issues.md): App() must remount the
// tenant-bound shell — not just clear the query cache — when the signed-in
// user changes, so component-local state (drafts, dispatch state, selected
// memo) never survives an account switch.

const mocks = vi.hoisted(() => ({
  userId: 'tenant-a',
  getToken: vi.fn(),
  shellMountCount: 0,
}));

vi.mock('@clerk/react-router', () => ({
  useAuth: () => ({
    getToken: mocks.getToken,
    isLoaded: true,
    isSignedIn: true,
    userId: mocks.userId,
  }),
}));

vi.mock('./api/auth', () => ({
  authedFetch: vi.fn().mockResolvedValue(new Response('{}', { status: 200 })),
  setTokenGetter: vi.fn(),
}));

// Stands in for AppFrame and every tenant-scoped descendant it hosts
// (Settings drafts, FlowPage memo state, useDispatchLookup) — one mount
// counter is enough to prove the whole subtree unmounted and remounted.
function MockAppFrame({ children }: { children: ReactNode }) {
  useEffect(() => {
    mocks.shellMountCount += 1;
  }, []);
  return <>{children}</>;
}
vi.mock('./components/AppFrame', () => ({ default: MockAppFrame }));

vi.mock('./components/ErrorBoundary', () => ({
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('./components/LoadingAnimation', () => ({ default: () => null }));
vi.mock('./components/LoginPage', () => ({ default: () => null }));
vi.mock('./pages/HomePage', () => ({ default: () => null }));
vi.mock('./pages/FlowPage', () => ({ default: () => null }));
vi.mock('./pages/PortfolioPage', () => ({ default: () => null }));
vi.mock('./pages/FundPage', () => ({ default: () => null }));

vi.mock('./hooks', () => ({ usePrefersReducedMotion: () => true }));
vi.mock('./hooks/useAgentsEnabled', () => ({ useAgentsEnabled: () => false }));
vi.mock('./hooks/useSystemData', () => ({
  useSystemData: () => ({
    authorityBlockedReason: null,
    authorityStatus: null,
    startupsError: null,
    startupsReady: true,
  }),
}));
vi.mock('./hooks/useForegroundSync', () => ({ useForegroundSync: () => undefined }));
vi.mock('./hooks/useActivitySummary', () => ({ useSinceAwaySummary: () => null }));
vi.mock('./lib/loginEntryTransition', () => ({
  getLoginEntryTransition: () => ({ appRevealMs: 0 }),
  LOGIN_ENTRY_SESSION_KEY: 'aethria.login-entry',
}));
vi.mock('./lib/warmStart', () => ({ clearWarmStartSnapshots: vi.fn() }));
vi.mock('framer-motion', () => ({
  motion: { div: ({ children }: { children: ReactNode }) => <div>{children}</div> },
  AnimatePresence: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

import App from './App';

function appTree(queryClient: QueryClient) {
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/v1']}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('tenant switch remounts the shell', () => {
  beforeEach(() => {
    mocks.userId = 'tenant-a';
    mocks.shellMountCount = 0;
    mocks.getToken.mockReset();
    mocks.getToken.mockResolvedValue('token');
    window.sessionStorage.clear();
  });

  it('unmounts and remounts the tenant-bound shell when the signed-in user changes', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(appTree(queryClient));

    await waitFor(() => expect(mocks.shellMountCount).toBe(1));

    mocks.userId = 'tenant-b';
    view.rerender(appTree(queryClient));

    await waitFor(() => expect(mocks.shellMountCount).toBe(2));
  });

  it('does not remount on the initial undefined-to-id transition (first load, not a switch)', async () => {
    mocks.userId = 'tenant-a';
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(appTree(queryClient));

    await waitFor(() => expect(mocks.shellMountCount).toBe(1));

    // Re-rendering with the SAME user must not force another remount.
    view.rerender(appTree(queryClient));
    await waitFor(() => expect(mocks.shellMountCount).toBe(1));
  });
});
