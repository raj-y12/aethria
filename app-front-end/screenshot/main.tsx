import React from 'react';
import ReactDOM from 'react-dom/client';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import '@fontsource-variable/figtree';
import '../src/index.css';
import '@aethria/product-chrome';
import { setTokenGetter } from '../src/api/auth';
import AppFrame from '../src/components/AppFrame';
import GrainOverlay from '../src/components/GrainOverlay';
import TodayPage from '../src/pages/TodayPage';
import FlowPage from '../src/pages/FlowPage';
import PortfolioPage from '../src/pages/PortfolioPage';
import FundPage from '../src/pages/FundPage';
import SettingsPage from '../src/settings/SettingsPage';
import { MOCK_SYSTEM_DATA, installMockApi } from './mock';

installMockApi();
setTokenGetter(async () => 'demo-token');

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false, refetchInterval: false } },
});

function Harness() {
  const { pathname } = useLocation();
  const isSettings = pathname.startsWith('/v1/settings');
  const isFund = pathname.startsWith('/v1/fund');
  const isPortfolio = pathname.startsWith('/v1/portfolio');
  const isFlow = pathname.startsWith('/v1/flow');
  const bare = !isSettings && !isFund && !isPortfolio && !isFlow;

  return (
    <div className="min-h-[100dvh]">
      <GrainOverlay opacity={0.028} />
      <AppFrame data={MOCK_SYSTEM_DATA} startupsError={null} chrome={bare ? 'bare' : 'full'}>
        {isSettings ? (
          <SettingsPage />
        ) : isPortfolio ? (
          <PortfolioPage data={MOCK_SYSTEM_DATA} />
        ) : isFund ? (
          <FundPage data={MOCK_SYSTEM_DATA} />
        ) : isFlow ? (
          <FlowPage data={MOCK_SYSTEM_DATA} />
        ) : (
          <TodayPage data={MOCK_SYSTEM_DATA} />
        )}
      </AppFrame>
    </div>
  );
}

const route = new URLSearchParams(window.location.search).get('route') ?? '/v1';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="*" element={<Harness />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
