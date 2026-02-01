import { useState, useCallback, useEffect } from 'react';
import HomePage from './components/HomePage';
import MainLayout from './components/MainLayout';
import LoadingAnimation from './components/LoadingAnimation';
import WaitingListPage from './waitingList/WaitingListPage';
import SettingsPage from './settings/SettingsPage';
import { fetchStartups } from './api/startups';
import { useIdleTimeout } from './hooks';
import type { Startup } from './types/startup';

const MIN_LOADING_MS = 2000;
const IDLE_MS = 20 * 60 * 1000;
const STORAGE_KEY = 'aethria_last_activity';
/** Poll interval to refetch startups when a decision has been made on the backend. */
const STARTUPS_POLL_MS = 12 * 1000;

function shouldResume(): boolean {
  if (typeof window === 'undefined') return false;
  const last = localStorage.getItem(STORAGE_KEY);
  if (!last) return false;
  const lastActivity = parseInt(last, 10);
  return !isNaN(lastActivity) && Date.now() - lastActivity < IDLE_MS;
}

const delay = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

function App() {
  const [showWorkGrid, setShowWorkGrid] = useState(shouldResume);
  const [isLoading, setIsLoading] = useState(shouldResume);
  const [startups, setStartups] = useState<Startup[]>([]);

  useEffect(() => {
    if (!showWorkGrid || !isLoading || startups.length > 0) return;
    const load = async () => {
      const [data] = await Promise.all([
        fetchStartups().catch(() => []),
        delay(MIN_LOADING_MS),
      ]);
      setStartups(data);
      setIsLoading(false);
    };
    void load();
  }, [showWorkGrid, isLoading, startups.length]);

  useEffect(() => {
    if (!showWorkGrid || isLoading) return;
    const refresh = () => {
      fetchStartups()
        .then((data) => setStartups(data))
        .catch(() => {});
    };
    const id = setInterval(refresh, STARTUPS_POLL_MS);
    return () => clearInterval(id);
  }, [showWorkGrid, isLoading]);

  const handleEnter = useCallback(() => {
    localStorage.setItem(STORAGE_KEY, Date.now().toString());
    setIsLoading(true);
    setStartups([]);

    const load = async () => {
      const [data] = await Promise.all([
        fetchStartups().catch(() => []),
        delay(MIN_LOADING_MS),
      ]);
      setStartups(data);
      setIsLoading(false);
      setShowWorkGrid(true);
    };

    void load();
  }, []);

  useIdleTimeout({
    timeoutMs: IDLE_MS,
    enabled: showWorkGrid && !isLoading,
    onIdle: useCallback(() => {
      localStorage.removeItem(STORAGE_KEY);
      setShowWorkGrid(false);
      setStartups([]);
    }, []),
    onActivity: useCallback((now: number) => {
      localStorage.setItem(STORAGE_KEY, now.toString());
    }, []),
  });

  const isWaitingListRoute =
    typeof window !== 'undefined' &&
    window.location.pathname.startsWith('/waiting-list');

  const isSettingsRoute =
    typeof window !== 'undefined' &&
    window.location.pathname.startsWith('/settings');

  if (isWaitingListRoute) {
    return <WaitingListPage />;
  }

  if (isSettingsRoute) {
    return <SettingsPage />;
  }

  if (isLoading) {
    return <LoadingAnimation message="Loading Intelligence Data" />;
  }

  if (!showWorkGrid) {
    return <HomePage onEnter={handleEnter} />;
  }

  return <MainLayout startups={startups} />;
}

export default App;
