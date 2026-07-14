import { useState, useLayoutEffect, useEffect, useRef, lazy, Suspense } from 'react';
import { useLocation, Navigate } from 'react-router';
import { useAuth } from '@clerk/react-router';
import { useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { setTokenGetter } from './api/auth';
import { triggerAgents } from './api/agents';
import AppFrame from './components/AppFrame';
import ErrorBoundary from './components/ErrorBoundary';
import HomePage from './pages/HomePage';
import FlowPage from './pages/FlowPage';
import PortfolioPage from './pages/PortfolioPage';
import FundPage from './pages/FundPage';
import LoadingAnimation from './components/LoadingAnimation';
const SettingsPage = lazy(() => import('./settings/SettingsPage'));
const AdminDashboardPage = lazy(() => import('./admin/AdminDashboardPage'));
import { useSystemData } from './hooks/useSystemData';
import { useAgentsEnabled } from './hooks/useAgentsEnabled';
import { usePrefersReducedMotion } from './hooks';
import LoginPage from './components/LoginPage';
import { getLoginEntryTransition, LOGIN_ENTRY_SESSION_KEY } from './lib/loginEntryTransition';
import { clearWarmStartSnapshots } from './lib/warmStart';

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
    flowPanelOpen: isFlowRoute,
    portfolioPanelOpen: isPortfolioRoute,
  });
  const agentsEnabled = useAgentsEnabled();

  // The login-entry handoff key is consumed here (captured into state above);
  // clearing it after mount keeps later AppShell remounts from re-animating.
  useEffect(() => {
    sessionStorage.removeItem(LOGIN_ENTRY_SESSION_KEY);
  }, []);

  // Wait for the first startups fetch to settle (instant when the cache is
  // warm-hydrated) before kicking off a pipeline cycle: the trigger's backend
  // work otherwise competes with the login burst of reads and delays first paint.
  useEffect(() => {
    if (!agentsEnabled || isSettingsRoute || !systemData.startupsReady || triggeredAgentsRef.current) return;
    triggeredAgentsRef.current = true;
    void triggerAgents().catch(() => {
      triggeredAgentsRef.current = false;
    });
  }, [agentsEnabled, isSettingsRoute, systemData.startupsReady]);

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
      <AppFrame
        data={systemData}
        startupsError={systemData.startupsError}
        // Bare = spine dissolves: the front door and Settings are both focused,
        // Dispatch-style takeovers with their own way back to the app.
        chrome={!isPortfolioRoute && !isFundRoute && !isFlowRoute ? 'bare' : 'full'}
      >
        <ErrorBoundary key={pathname} label="workspace">
          {isSettingsRoute ? (
            <Suspense fallback={<LoadingAnimation />}>
              <SettingsPage />
            </Suspense>
          ) : isPortfolioRoute ? (
            <PortfolioPage data={systemData} />
          ) : isFundRoute ? (
            <FundPage data={systemData} />
          ) : isFlowRoute ? (
            <FlowPage data={systemData} />
          ) : (
            <HomePage data={systemData} />
          )}
        </ErrorBoundary>
      </AppFrame>
    </motion.div>
  );
}

function App() {
  const { pathname } = useLocation();
  const { isLoaded, isSignedIn, getToken, userId } = useAuth();
  const queryClient = useQueryClient();
  const [tokenReady, setTokenReady] = useState(false);
  const loginEntryHandoffRef = useRef(false);

  // The query cache is a module-level singleton, so it survives sign-out →
  // sign-in within the same SPA session. Without clearing it, a different
  // account that logs in next reads the previous tenant's cached data until a
  // hard reload. Drop the entire cache whenever the signed-in user changes
  // (account switch or sign-out). The initial undefined → id assignment is
  // skipped so we never clear a freshly-populated cache on first load.
  // useLayoutEffect (not useEffect) so the cache is cleared before the browser
  // paints the frame for the new identity — a passive effect runs a tick later,
  // after AppShell has already rendered the previous tenant's cached startups/
  // memos/settings, briefly showing one account's confidential data under another.
  const prevUserIdRef = useRef<string | null | undefined>(undefined);
  useLayoutEffect(() => {
    const prev = prevUserIdRef.current;
    if (prev !== undefined && prev !== userId) {
      queryClient.clear();
    }
    prevUserIdRef.current = userId;
  }, [userId, queryClient]);

  useLayoutEffect(() => {
    if (!isSignedIn) {
      loginEntryHandoffRef.current = false;
      setTokenGetter(null);
      setTokenReady(false);
      clearWarmStartSnapshots();
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
      <ErrorBoundary label="admin">
        <Suspense fallback={<LoadingAnimation />}>
          <AdminDashboardPage />
        </Suspense>
      </ErrorBoundary>
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
