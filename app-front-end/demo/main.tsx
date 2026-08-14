import React, { useEffect, useRef, useState } from 'react';
import ReactDOM from 'react-dom/client';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import '@fontsource/instrument-sans/400.css';
import '@fontsource/instrument-sans/500.css';
import '@fontsource/instrument-sans/600.css';
import '../src/index.css';
import './demo.css';
import '@aethria/product-chrome';
import { setTokenGetter } from '../src/api/auth';
import AppFrame from '../src/components/AppFrame';
import HomePage from '../src/pages/HomePage';
import FlowPage from '../src/pages/FlowPage';
import PortfolioPage from '../src/pages/PortfolioPage';
import FundPage from '../src/pages/FundPage';
import { MOCK_SYSTEM_DATA, installMockApi } from '../screenshot/mock';

/**
 * Public product demo — the real operator console rendered against illustrative
 * sample data, with Clerk and the backend stubbed out (see vite.demo.config.ts).
 *
 * Deliberately separate from screenshot/main.tsx: this entry carries the sample
 * data notice, which must never leak into generated marketing screenshots.
 *
 * Routing is in-memory. The console navigates normally (spine, deal → memo)
 * without touching the address bar, so the whole demo is one static page and
 * needs no server-side route handling.
 */
installMockApi();
setTokenGetter(async () => 'demo-token');

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false, refetchInterval: false } },
});

/** Standing, dismissible notice. The data below it is invented, and says so. */
function SampleDataNotice() {
  const [open, setOpen] = useState(true);
  const ref = useRef<HTMLDivElement | null>(null);

  // Reserve the notice's real height so the console shrinks to fit rather than
  // being overlapped. Observed rather than measured once: a single read can land
  // before fonts settle, and the line wraps to two on narrow viewports.
  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle('demo-notice-open', open);
    if (!open) {
      root.style.setProperty('--demo-notice-h', '0px');
      return;
    }
    const el = ref.current;
    if (!el) return;
    const sync = () => root.style.setProperty('--demo-notice-h', `${el.offsetHeight}px`);
    sync();
    const observer = new ResizeObserver(sync);
    observer.observe(el);
    return () => {
      observer.disconnect();
      root.classList.remove('demo-notice-open');
      root.style.removeProperty('--demo-notice-h');
    };
  }, [open]);

  if (!open) return null;
  return (
    <div
      ref={ref}
      role="note"
      style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '1rem',
        flexWrap: 'wrap',
        padding: '0.7rem 1rem',
        backgroundColor: 'var(--color-oxford)',
        color: 'var(--color-paper)',
        fontFamily: 'var(--font-mono)',
        fontSize: '10px',
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
      }}
    >
      <span>
        Interactive demo · every company, score and ruling below is illustrative sample data
      </span>
      <button
        type="button"
        onClick={() => setOpen(false)}
        style={{
          background: 'none',
          border: '1px solid currentColor',
          color: 'inherit',
          font: 'inherit',
          cursor: 'pointer',
          padding: '0.3rem 0.7rem',
        }}
      >
        Dismiss
      </button>
    </div>
  );
}

function Demo() {
  const { pathname } = useLocation();
  const isFund = pathname.startsWith('/v1/fund');
  const isPortfolio = pathname.startsWith('/v1/portfolio');
  const isFlow = pathname.startsWith('/v1/flow');
  const bare = !isFund && !isPortfolio && !isFlow;

  return (
    <div className="min-h-[100dvh]">
      <AppFrame data={MOCK_SYSTEM_DATA} startupsError={null} chrome={bare ? 'bare' : 'full'}>
        {isPortfolio ? (
          <PortfolioPage data={MOCK_SYSTEM_DATA} />
        ) : isFund ? (
          <FundPage data={MOCK_SYSTEM_DATA} />
        ) : isFlow ? (
          <FlowPage data={MOCK_SYSTEM_DATA} />
        ) : (
          <HomePage data={MOCK_SYSTEM_DATA} />
        )}
      </AppFrame>
      <SampleDataNotice />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/v1/flow']}>
        <Routes>
          <Route path="*" element={<Demo />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
