import React from 'react';
import ReactDOM from 'react-dom/client';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import '@fontsource-variable/figtree';
import '../src/index.css';
import '@aethria/product-chrome';
import { setTokenGetter } from '../src/api/auth';
import AppFrame from '../src/components/AppFrame';
import HomePage from '../src/pages/HomePage';
import FlowPage from '../src/pages/FlowPage';
import PortfolioPage from '../src/pages/PortfolioPage';
import FundPage from '../src/pages/FundPage';
import SettingsPage from '../src/settings/SettingsPage';
import LoginPage from '../src/components/LoginPage';
import { MOCK_SYSTEM_DATA, installMockApi } from './mock';
import type { SystemData } from '../src/hooks/useSystemData';

/** ?empty=1 — a fresh fund with nothing in the pipeline (zero-state review). */
const EMPTY_DATA: SystemData = {
  ...MOCK_SYSTEM_DATA,
  startups: [],
  signals: [],
  metaReports: [],
  pendingEscalationCount: 0,
  watchlistAnalytics: { total: 0, stale: 0, avg_days: 0, entries: [] } as never,
  concentrationAnalytics: { by_sector: {}, most_concentrated_sector: '', most_concentrated_theme: '', last_updated: '' } as never,
};

installMockApi();
setTokenGetter(async () => 'demo-token');

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false, refetchInterval: false } },
});

function Harness({ data }: { data: SystemData }) {
  const { pathname } = useLocation();
  if (pathname.startsWith('/sign-in')) {
    return <LoginPage />;
  }
  const isSettings = pathname.startsWith('/v1/settings');
  const isFund = pathname.startsWith('/v1/fund');
  const isPortfolio = pathname.startsWith('/v1/portfolio');
  const isFlow = pathname.startsWith('/v1/flow');
  const bare = !isSettings && !isFund && !isPortfolio && !isFlow;

  return (
    <div className="min-h-[100dvh]">
      <AppFrame data={data} startupsError={null} chrome={bare ? 'bare' : 'full'}>
        {isSettings ? (
          <SettingsPage />
        ) : isPortfolio ? (
          <PortfolioPage data={data} />
        ) : isFund ? (
          <FundPage data={data} />
        ) : isFlow ? (
          <FlowPage data={data} />
        ) : (
          <HomePage data={data} />
        )}
      </AppFrame>
    </div>
  );
}

const params = new URLSearchParams(window.location.search);
const route = params.get('route') ?? '/v1';
const harnessData = params.get('empty') === '1' ? EMPTY_DATA : MOCK_SYSTEM_DATA;

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="*" element={<Harness data={harnessData} />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
