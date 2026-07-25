import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  fetchStartups: vi.fn(),
  fetchSystemStatus: vi.fn(),
  fetchFundThesisRuntime: vi.fn(),
  fetchSettings: vi.fn(),
}));

vi.mock('../api/startups', () => ({ fetchStartups: api.fetchStartups }));
vi.mock('../api/system', () => ({ fetchSystemStatus: api.fetchSystemStatus }));
vi.mock('../api/fundThesis', () => ({ fetchFundThesisRuntime: api.fetchFundThesisRuntime }));
vi.mock('../api/settings', () => ({ fetchSettings: api.fetchSettings }));
vi.mock('../api/escalations', () => ({ fetchEscalations: vi.fn() }));
vi.mock('../api/signals', () => ({ fetchSignals: vi.fn() }));
vi.mock('../api/analytics', () => ({
  fetchRejectionAnalytics: vi.fn(), fetchWatchlistAnalytics: vi.fn(),
  fetchConcentrationAnalytics: vi.fn(), fetchSystemHealth: vi.fn(),
}));
vi.mock('../api/meta', () => ({
  fetchMetaReports: vi.fn(), fetchMetaPromptState: vi.fn(), fetchMetaEvalSet: vi.fn(),
  fetchScoutWeights: vi.fn(), fetchCalibrationState: vi.fn(), fetchMetaInsights: vi.fn(),
}));
vi.mock('../lib/queryIntent', () => ({ getQueryConfig: () => ({}) }));
vi.mock('../lib/warmStart', () => ({ useWarmStart: vi.fn() }));
vi.mock('./useQueryLiveGate', () => ({ useQueryLiveGate: () => ({ tabVisible: true, userActive: true }) }));
vi.mock('./useStartupsStream', () => ({ useStartupsStream: () => false }));
vi.mock('./useAuthority', () => ({
  useAuthority: () => ({
    status: {
      mode: 'canonical_read', version: 4, kill_switch: false,
      canonical_writes_allowed: false, canonical_reads_allowed: true,
      last_reconciliation_status: 'green',
    },
    isCanonicalRead: true,
    isCanonicalWrite: false,
    blockedReason: null,
    refetch: vi.fn(),
  }),
}));

import { useSystemData } from './useSystemData';

function wrapper(queryClient: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useSystemData authority handoff', () => {
  beforeEach(() => {
    localStorage.clear();
    api.fetchStartups.mockReset();
    api.fetchSystemStatus.mockReset();
    api.fetchFundThesisRuntime.mockReset();
    api.fetchSettings.mockReset();
    api.fetchStartups.mockResolvedValue([{ id: 'startup-1' }]);
    api.fetchSystemStatus.mockResolvedValue({ status: 'ok', durable_jobs: { required: false, ready: true, error: null, counts: {} } });
    api.fetchFundThesisRuntime.mockResolvedValue({ mode: 'missing' });
    api.fetchSettings.mockResolvedValue(null);
  });

  it('keeps the legacy startup queue active on a cold canonical-read load until a canonical DTO exists', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useSystemData(), { wrapper: wrapper(queryClient) });

    await waitFor(() => {
      expect(api.fetchStartups).toHaveBeenCalledTimes(1);
      expect(result.current.startups).toEqual([{ id: 'startup-1' }]);
    });
  });
});
