import { useState, useLayoutEffect, useEffect, useRef } from 'react';
import { useLocation, Navigate } from 'react-router';
import { useAuth } from '@clerk/react-router';
import { setTokenGetter } from './api/auth';
import { triggerAgents } from './api/agents';
import MainLayout from './components/MainLayout';
import GrainOverlay from './components/GrainOverlay';
import LoadingAnimation from './components/LoadingAnimation';
import SettingsPage from './settings/SettingsPage';
import { useSystemData } from './hooks/useSystemData';
import LoginPage from './components/LoginPage';

const APP_ROOT = '/v1';

function AppShell() {
  const { pathname } = useLocation();
  const isSettingsRoute = pathname.startsWith('/settings');
  const [isSystemPanelOpen, setIsSystemPanelOpen] = useState(false);
  const [isLookupActive, setIsLookupActive] = useState(false);
  const systemData = useSystemData({
    systemPanelOpen: !isSettingsRoute && isSystemPanelOpen,
    lookupActive: !isSettingsRoute && isLookupActive,
  });
  const hasTriggeredAgents = useRef(false);
  useEffect(() => {
    if (hasTriggeredAgents.current) return;
    hasTriggeredAgents.current = true;
    triggerAgents().catch(() => {});
  }, []);

  useEffect(() => {
    if (!isSettingsRoute) return;
    setIsSystemPanelOpen(false);
    setIsLookupActive(false);
  }, [isSettingsRoute]);

  return (
    <>
      <GrainOverlay opacity={0.02} />
      {isSettingsRoute ? (
        <SettingsPage />
      ) : (
        <MainLayout
          data={systemData}
          onSystemPanelOpenChange={setIsSystemPanelOpen}
          onLookupActiveChange={setIsLookupActive}
        />
      )}
    </>
  );
}

function App() {
  const { pathname } = useLocation();
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const [tokenReady, setTokenReady] = useState(false);

  useLayoutEffect(() => {
    if (!isSignedIn) {
      setTokenGetter(null);
      setTokenReady(false);
      return;
    }
    setTokenGetter(getToken);
    return () => setTokenGetter(null);
  }, [isSignedIn, getToken]);

  useEffect(() => {
    if (!isSignedIn || !getToken) {
      setTokenReady(false);
      return;
    }
    let cancelled = false;
    const fallback = setTimeout(() => {
      if (!cancelled) setTokenReady(true);
    }, 5000);

    async function tryGetToken(retries = 5) {
      for (let i = 0; i < retries && !cancelled; i++) {
        const t = await getToken();
        if (t) {
          if (!cancelled) setTokenReady(true);
          return;
        }
        await new Promise((r) => setTimeout(r, 300));
      }
      if (!cancelled) setTokenReady(true);
    }
    tryGetToken();

    return () => {
      cancelled = true;
      clearTimeout(fallback);
    };
  }, [isSignedIn, getToken]);

  const isSignInRoute = pathname.startsWith('/sign-in');
  const isAppRoute = pathname === APP_ROOT || pathname.startsWith(APP_ROOT + '/');
  const isSettingsRoute = pathname.startsWith('/settings');

  // Sign-in page: show login (LoginPage does full-page redirect to /v1 on success)
  if (isSignInRoute) {
    return <LoginPage />;
  }

  // App routes: require sign-in, then wait for token before fetching
  if (isAppRoute || isSettingsRoute) {
    if (!isLoaded) {
      return <LoadingAnimation />;
    }
    if (!isSignedIn) {
      return <Navigate to="/sign-in" replace />;
    }
    if (!tokenReady) {
      return <LoadingAnimation />;
    }
    return <AppShell />;
  }

  // Root or unknown path → go to app (or sign-in if not signed in)
  if (!isLoaded) {
    return <LoadingAnimation />;
  }
  if (!isSignedIn) {
    return <Navigate to="/sign-in" replace />;
  }
  return <Navigate to={APP_ROOT} replace />;
}

export default App;
export { APP_ROOT };
