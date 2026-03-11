import { useState, useCallback, useEffect } from 'react';
import EnterSystemPage from './components/EnterSystemPage';
import MainLayout from './components/MainLayout';
import LoadingAnimation from './components/LoadingAnimation';
import GrainOverlay from './components/GrainOverlay';
import SettingsPage from './settings/SettingsPage';
import { fetchStartups } from './api/startups';
import { useIdleTimeout } from './hooks';
import type { Startup } from './types/startup';

const MIN_LOADING_MS = 2000;
const IDLE_MS = 20 * 60 * 1000;
const STORAGE_KEY = 'aethria_last_activity';
/** Poll interval to refetch startups when a decision has been made on the backend. */
const STARTUPS_POLL_MS = 12 * 1000;

function hasValidSession(): boolean {
  if (typeof window === 'undefined') return false;
  // When opened from /private-access, force fresh login every time
  const params = new URLSearchParams(window.location.search);
  if (params.get('forceLogin') === '1') {
    localStorage.removeItem(STORAGE_KEY);
    return false;
  }
  const last = localStorage.getItem(STORAGE_KEY);
  if (!last) return false;
  const lastActivity = parseInt(last, 10);
  return !isNaN(lastActivity) && Date.now() - lastActivity < IDLE_MS;
}

const delay = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

function App() {
  const sessionValid = hasValidSession();
  const [hasEntered, setHasEntered] = useState(sessionValid);
  const [isLoading, setIsLoading] = useState(sessionValid);
  const [startups, setStartups] = useState<Startup[]>([]);
  const [startupsError, setStartupsError] = useState<string | null>(null);

  useEffect(() => {
    if (!hasEntered || isLoading) return;
    setStartupsError(null);
    const refresh = () => {
      fetchStartups()
        .then((data) => {
          setStartups(data);
          setStartupsError(null);
        })
        .catch((err) => setStartupsError(err instanceof Error ? err.message : 'Failed to load'));
    };
    const id = setInterval(refresh, STARTUPS_POLL_MS);
    return () => clearInterval(id);
  }, [hasEntered, isLoading]);

  useEffect(() => {
    if (!hasEntered || !isLoading) return;
    setStartupsError(null);
    const load = async () => {
      const [data] = await Promise.all([
        fetchStartups().catch((e: unknown) => {
          setStartupsError(e instanceof Error ? e.message : 'Failed to load startups');
          return [] as Startup[];
        }),
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
      <MainLayout startups={startups} startupsError={startupsError} />
    </>
  );
}

export default App;
