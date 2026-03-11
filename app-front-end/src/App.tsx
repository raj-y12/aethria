import { useState, useCallback } from 'react';
import EnterSystemPage from './components/EnterSystemPage';
import MainLayout from './components/MainLayout';
import LoadingAnimation from './components/LoadingAnimation';
import GrainOverlay from './components/GrainOverlay';
import SettingsPage from './settings/SettingsPage';
import { useIdleTimeout } from './hooks';
import { useSystemData } from './hooks/useSystemData';

const MIN_LOADING_MS = 2000;
const IDLE_MS = 20 * 60 * 1000;
const STORAGE_KEY = 'aethria_last_activity';
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
  // System-wide data (startups, escalations, signals, analytics, meta, settings)
  const systemData = useSystemData();

  if (hasEntered && isLoading) {
    // Initial loading state: give the loader at least MIN_LOADING_MS
    setTimeout(() => setIsLoading(false), MIN_LOADING_MS);
  }

  const handleEnter = useCallback(() => {
    localStorage.setItem(STORAGE_KEY, Date.now().toString());
    setHasEntered(true);
    setIsLoading(true);
  }, []);

  useIdleTimeout({
    timeoutMs: IDLE_MS,
    enabled: hasEntered && !isLoading,
    onIdle: useCallback(() => {
      localStorage.removeItem(STORAGE_KEY);
      setHasEntered(false);
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
      <MainLayout data={systemData} />
    </>
  );
}

export default App;
