import { useState, useCallback } from 'react';
import MainLayout from './components/MainLayout';
import LoadingAnimation from './components/LoadingAnimation';
import GrainOverlay from './components/GrainOverlay';
import LoginPage from './components/LoginPage';
import SettingsPage from './settings/SettingsPage';
import { useIdleTimeout } from './hooks';
import { useSystemData } from './hooks/useSystemData';

const MIN_LOADING_MS = 2000;
const IDLE_MS = 20 * 60 * 1000;
const STORAGE_KEY = 'aethria_last_activity';

function hasAuth(): boolean {
  if (typeof window === 'undefined') return false;
  return sessionStorage.getItem('auth') === 'true';
}

function hasValidSession(): boolean {
  if (typeof window === 'undefined') return false;
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

function App() {
  const [auth, setAuth] = useState(() => hasAuth());
  const sessionValid = hasValidSession();
  const [hasEntered, setHasEntered] = useState(() => sessionValid || hasAuth());
  const [isLoading, setIsLoading] = useState(() => sessionValid || hasAuth());
  const systemData = useSystemData();

  if (hasEntered && isLoading) {
    setTimeout(() => setIsLoading(false), MIN_LOADING_MS);
  }

  const handleLoginSuccess = useCallback(() => {
    localStorage.setItem(STORAGE_KEY, Date.now().toString());
    setAuth(true);
    setHasEntered(true);
    setIsLoading(true);
  }, []);

  useIdleTimeout({
    timeoutMs: IDLE_MS,
    enabled: auth && hasEntered && !isLoading,
    onIdle: useCallback(() => {
      sessionStorage.removeItem('auth');
      localStorage.removeItem(STORAGE_KEY);
      setAuth(false);
      setHasEntered(false);
    }, []),
    onActivity: useCallback((now: number) => {
      localStorage.setItem(STORAGE_KEY, now.toString());
    }, []),
  });

  const isSettingsRoute =
    typeof window !== 'undefined' &&
    window.location.pathname.startsWith('/settings');

  if (!auth) {
    return (
      <>
        <GrainOverlay opacity={0.02} />
        <LoginPage onSuccess={handleLoginSuccess} />
      </>
    );
  }

  if (isLoading) {
    return (
      <>
        <GrainOverlay opacity={0.02} />
        <LoadingAnimation />
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
