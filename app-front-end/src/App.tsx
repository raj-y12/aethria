import { useState, useLayoutEffect, useEffect, lazy, Suspense } from 'react';
import { useLocation, Navigate } from 'react-router';
import { useAuth } from '@clerk/react-router';
import { setTokenGetter } from './api/auth';
import MainLayout from './components/MainLayout';
import GrainOverlay from './components/GrainOverlay';
import LoadingAnimation from './components/LoadingAnimation';
const SettingsPage = lazy(() => import('./settings/SettingsPage'));
const AdminDashboardPage = lazy(() => import('./admin/AdminDashboardPage'));
import WhileYouWereAway from './components/WhileYouWereAway';
import { useSystemData } from './hooks/useSystemData';
import { useAgentsEnabled } from './hooks/useAgentsEnabled';
import { useActivitySummary } from './hooks/useActivitySummary';
import LoginPage from './components/LoginPage';

const APP_ROOT = '/v1';
const SETTINGS_ROOT = `${APP_ROOT}/settings`;
const ADMIN_ROOT = '/admin';

function AppShell() {
  const { pathname } = useLocation();
  const isSettingsRoute = pathname.startsWith(SETTINGS_ROOT);
  const [isSystemPanelOpen, setIsSystemPanelOpen] = useState(false);
  const systemData = useSystemData({
    systemPanelOpen: !isSettingsRoute && isSystemPanelOpen,
  });
  const agentsEnabled = useAgentsEnabled();
  const { summary, showSummary, loading, dismissSummary } = useActivitySummary();

  // Warn the user before closing the tab if agents are actively running.
  useEffect(() => {
    if (!agentsEnabled) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      // Modern browsers show a generic message; setting returnValue is required for the dialog to appear.
      e.returnValue = 'Agents are currently running. Are you sure you want to leave?';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [agentsEnabled]);

  useEffect(() => {
    if (!isSettingsRoute) return;
    setIsSystemPanelOpen(false);
  }, [isSettingsRoute]);

  if (loading) {
    return <LoadingAnimation />;
  }

  if (showSummary && summary) {
    return <WhileYouWereAway summary={summary} onDismiss={dismissSummary} />;
  }

  return (
    <>
      <GrainOverlay opacity={0.02} />
      {isSettingsRoute ? (
        <Suspense fallback={<LoadingAnimation />}>
          <SettingsPage />
        </Suspense>
      ) : (
        <MainLayout
          data={systemData}
          startupsError={systemData.startupsError}
          onSystemPanelOpenChange={setIsSystemPanelOpen}
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
  const isAdminRoute = pathname === ADMIN_ROOT || pathname.startsWith(ADMIN_ROOT + '/');
  const isAppRoute = pathname === APP_ROOT || pathname.startsWith(APP_ROOT + '/');
  const isSettingsRoute = pathname.startsWith(SETTINGS_ROOT);

  if (isAdminRoute) {
    return (
      <Suspense fallback={<LoadingAnimation />}>
        <AdminDashboardPage />
      </Suspense>
    );
  }

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
