import { useState, useCallback, useEffect } from 'react';
import EnterSystemPage from './components/EnterSystemPage';
import MainLayout from './components/MainLayout';
import LoadingAnimation from './components/LoadingAnimation';
import GrainOverlay from './components/GrainOverlay';
import SettingsPage from './settings/SettingsPage';
import { fetchStartups } from './api/startups';
import { useIdleTimeout, useSystemData } from './hooks';
import type { Startup } from './types/startup';

const MIN_LOADING_MS = 2000;
const IDLE_MS = 20 * 60 * 1000;
const STORAGE_KEY = 'aethria_last_activity';

function hasValidSession(): boolean {
  if (typeof window === 'undefined') return false;
  const last = localStorage.getItem(STORAGE_KEY);
  if (!last) return false;
  const lastActivity = parseInt(last, 10);
  return !isNaN(lastActivity) && Date.now() - lastActivity < IDLE_MS;
}

const delay = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

function SystemLayout() {
  const sys = useSystemData();
  return (
    <MainLayout
      startups={sys.startups}
      signals={sys.signals}
      escalations={sys.escalations}
      metaReports={sys.metaReports}
      rejectionAnalytics={sys.rejectionAnalytics}
      watchlistAnalytics={sys.watchlistAnalytics}
      concentrationAnalytics={sys.concentrationAnalytics}
      scoutWeights={sys.scoutWeights}
      calibrationState={sys.calibrationState}
      pendingEscalationCount={sys.pendingEscalationCount}
    />
  );
}

function App() {
  const sessionValid = hasValidSession();
  const [hasEntered, setHasEntered] = useState(sessionValid);
  const [isLoading, setIsLoading] = useState(sessionValid);
  const [, setStartups] = useState<Startup[]>([]);

  useEffect(() => {
    if (!hasEntered || !isLoading) return;
    const load = async () => {
      const [data] = await Promise.all([
        fetchStartups().catch(() => []),
        delay(MIN_LOADING_MS),
      ]);
      setStartups(data);
      setIsLoading(false);
    };
    void load();
  }, [hasEntered, isLoading]);

  const handleEnter = useCallback(() => {
    localStorage.setItem(STORAGE_KEY, Date.now().toString());
    setHasEntered(true);
    setStartups([]);

    const load = async () => {
      const [data] = await Promise.all([
        fetchStartups().catch(() => []),
        delay(0),
      ]);
      setStartups(data);
    };

    void load();
  }, []);

  useIdleTimeout({
    timeoutMs: IDLE_MS,
    enabled: hasEntered && !isLoading,
    onIdle: useCallback(() => {
      localStorage.removeItem(STORAGE_KEY);
      setHasEntered(false);
      setStartups([]);
    }, []),
    onActivity: useCallback((now: number) => {
      localStorage.setItem(STORAGE_KEY, now.toString());
    }, []),
  });

  const isSettingsRoute =
    typeof window !== 'undefined' &&
    window.location.pathname.startsWith('/settings');

  if (isLoading) {
    return (
      <>
        <GrainOverlay opacity={0.02} />
        <LoadingAnimation />
      </>
    );
  }

  if (!hasEntered) {
    return (
      <>
        <GrainOverlay opacity={0.02} />
        <EnterSystemPage onEnter={handleEnter} />
      </>
    );
  }

  if (isSettingsRoute) {
    return (
      <>
        <GrainOverlay opacity={0.02} />
        <SettingsPage />
      </>
    );
  }

  return (
    <>
      <GrainOverlay opacity={0.02} />
      <SystemLayout />
    </>
  );
}

export default App;
