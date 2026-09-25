import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  agentsEnabled: true,
  authedFetch: vi.fn(),
  getToken: vi.fn(),
  startupsReady: true,
}));

vi.mock('@clerk/react-router', () => ({
  useAuth: () => ({
    getToken: mocks.getToken,
    isLoaded: true,
    isSignedIn: true,
    userId: 'user-agent-trigger-test',
  }),
}));

vi.mock('./api/auth', () => ({
  authedFetch: mocks.authedFetch,
  setTokenGetter: vi.fn(),
}));

vi.mock('./components/AppFrame', () => ({
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

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
vi.mock('./hooks/useAgentsEnabled', () => ({ useAgentsEnabled: () => mocks.agentsEnabled }));
vi.mock('./hooks/useSystemData', () => ({
  useSystemData: () => ({
    authorityBlockedReason: null,
    authorityStatus: null,
    startupsError: null,
    startupsReady: mocks.startupsReady,
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
import { triggerAgents } from './api/agents';

function appTree(queryClient: QueryClient) {
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/v1']}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('agent trigger failures', () => {
  beforeEach(() => {
    mocks.agentsEnabled = true;
    mocks.authedFetch.mockReset();
    mocks.getToken.mockReset();
    mocks.getToken.mockResolvedValue('token');
    mocks.startupsReady = true;
    window.sessionStorage.clear();
  });

  it('rejects a JSON 503 response from the agent trigger endpoint', async () => {
    mocks.authedFetch.mockResolvedValue(new Response(JSON.stringify({
      status: 'unavailable',
      reason: 'worker_not_ready',
    }), { status: 503 }));

    await expect(triggerAgents()).rejects.toThrow('Agent trigger failed: 503');
  });

  it('releases the initial trigger guard after a failed trigger so a later ready event can retry', async () => {
    mocks.authedFetch
      .mockResolvedValueOnce(new Response(JSON.stringify({
        status: 'unavailable',
        reason: 'worker_not_ready',
      }), { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: 'queued' }), { status: 202 }));
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(appTree(queryClient));

    await waitFor(() => expect(mocks.authedFetch).toHaveBeenCalledTimes(1));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    mocks.startupsReady = false;
    view.rerender(appTree(queryClient));
    mocks.startupsReady = true;
    view.rerender(appTree(queryClient));

    await waitFor(() => expect(mocks.authedFetch).toHaveBeenCalledTimes(2));
  });
});
