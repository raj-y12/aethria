import { useState, useLayoutEffect, useEffect, useRef, lazy, Suspense } from 'react';
import { useLocation, Navigate } from 'react-router';
import { useAuth } from '@clerk/react-router';
import { motion } from 'framer-motion';
import { setTokenGetter } from './api/auth';
import { triggerAgents } from './api/agents';
import AppFrame from './components/AppFrame';
import TodayPage from './pages/TodayPage';
import FlowPage from './pages/FlowPage';
import PortfolioPage from './pages/PortfolioPage';
import FundPage from './pages/FundPage';
import GrainOverlay from './components/GrainOverlay';
import LoadingAnimation from './components/LoadingAnimation';
const SettingsPage = lazy(() => import('./settings/SettingsPage'));
const AdminDashboardPage = lazy(() => import('./admin/AdminDashboardPage'));
import WhileYouWereAway from './components/WhileYouWereAway';
import { useSystemData } from './hooks/useSystemData';
import { useAgentsEnabled } from './hooks/useAgentsEnabled';
import { useActivitySummary } from './hooks/useActivitySummary';
import { usePrefersReducedMotion } from './hooks';
import LoginPage from './components/LoginPage';
import { getLoginEntryTransition, LOGIN_ENTRY_SESSION_KEY } from './lib/loginEntryTransition';

const APP_ROOT = '/v1';
const SETTINGS_ROOT = `${APP_ROOT}/settings`;
const ADMIN_ROOT = '/admin';

function AppShell() {
  const { pathname } = useLocation();
  const isSettingsRoute = pathname.startsWith(SETTINGS_ROOT);
  const isFundRoute = pathname.startsWith(`${APP_ROOT}/fund`);
  const isPortfolioRoute = pathname.startsWith(`${APP_ROOT}/portfolio`);
  const isFlowRoute = pathname.startsWith(`${APP_ROOT}/flow`) || pathname.startsWith(`${APP_ROOT}/deal`);
  const [arrivedFromLogin] = useState(() => sessionStorage.getItem(LOGIN_ENTRY_SESSION_KEY) === '1');
  const triggeredAgentsRef = useRef(false);
  const reduceMotion = usePrefersReducedMotion();
  const entryTransition = getLoginEntryTransition(reduceMotion);
  const systemData = useSystemData({
    // The Fund workspace surfaces meta/analytics — refresh them when it opens.
    systemPanelOpen: !isSettingsRoute && isFundRoute,
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
    if (!agentsEnabled || isSettingsRoute || triggeredAgentsRef.current) return;
    triggeredAgentsRef.current = true;
    void triggerAgents().catch(() => {
      triggeredAgentsRef.current = false;
    });
  }, [agentsEnabled, isSettingsRoute]);

  if (loading && !arrivedFromLogin) {
    return <LoadingAnimation />;
  }

  if (showSummary && summary) {
    return <WhileYouWereAway summary={summary} onDismiss={dismissSummary} />;
  }

  return (
    <motion.div
      className="min-h-[100dvh]"
      initial={
        arrivedFromLogin
          ? reduceMotion
            ? { opacity: 0 }
            : { opacity: 0, y: 16 }
          : false
      }
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: entryTransition.appRevealMs / 1000, ease: [0.16, 1, 0.3, 1] }}
    >
      <GrainOverlay opacity={0.028} />
      {isSettingsRoute ? (
        <Suspense fallback={<LoadingAnimation />}>
          <SettingsPage />
        </Suspense>
      ) : (
        <AppFrame data={systemData} startupsError={systemData.startupsError}>
          {isPortfolioRoute ? (
            <PortfolioPage data={systemData} />
          ) : isFundRoute ? (
            <FundPage data={systemData} />
          ) : isFlowRoute ? (
            <FlowPage data={systemData} />
          ) : (
            <TodayPage data={systemData} />
          )}
        </AppFrame>
      )}
    </motion.div>
  );
}

function App() {
  const { pathname } = useLocation();
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const [tokenReady, setTokenReady] = useState(false);
  const loginEntryHandoffRef = useRef(false);

  useLayoutEffect(() => {
    if (!isSignedIn) {
      loginEntryHandoffRef.current = false;
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

    async function waitForToken() {
      while (!cancelled) {
        const t = await getToken();
        if (t) {
          if (!cancelled) setTokenReady(true);
          return;
        }
        await new Promise((r) => setTimeout(r, 500));
      }
    }
    waitForToken();

    return () => {
      cancelled = true;
    };
  }, [isSignedIn, getToken]);

  const isSignInRoute = pathname.startsWith('/sign-in');
  const isAdminRoute = pathname === ADMIN_ROOT || pathname.startsWith(ADMIN_ROOT + '/');
  const isAppRoute = pathname === APP_ROOT || pathname.startsWith(APP_ROOT + '/');
  const isSettingsRoute = pathname.startsWith(SETTINGS_ROOT);
  if ((isAppRoute || isSettingsRoute) && sessionStorage.getItem(LOGIN_ENTRY_SESSION_KEY) === '1') {
    loginEntryHandoffRef.current = true;
  }
  const hasLoginEntryHandoff = loginEntryHandoffRef.current;

  if (isAdminRoute) {
    return (
      <>
        <GrainOverlay opacity={0.028} />
        <Suspense fallback={<LoadingAnimation />}>
          <AdminDashboardPage />
        </Suspense>
      </>
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
    if (!tokenReady && !hasLoginEntryHandoff) {
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
