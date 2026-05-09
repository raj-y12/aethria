import { Suspense, lazy, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import SystemAccessPage from './SystemAccessPage';
import HomePage from '../HomePage';
import RequestAccessPage from '../RequestAccessPage';

const DURATION = 0.3;
const EASE: [number, number, number, number] = [0.16, 1, 0.3, 1];
const PAPER = '#e9e0d1';
const OXFORD = '#1d2d48';

// Private routes: any file in src/private/*.tsx is exposed at /<filename-lowercase>.
// Delete the file to remove that route at build time.
const privateModules = import.meta.glob<{ default: React.ComponentType }>('../private/*.tsx');
const privateRoutes: Record<string, React.LazyExoticComponent<React.ComponentType>> = {};
for (const key of Object.keys(privateModules)) {
  const segment = key.replace(/^\.\.\/private\//, '').replace(/\.tsx$/, '').toLowerCase();
  if (segment) {
    const path = '/' + segment;
    privateRoutes[path] = lazy(privateModules[key] as () => Promise<{ default: React.ComponentType }>);
  }
}

const PUBLIC_PATHS = ['/', '/home', '/request-access'];

export default function AnimatedRoutes() {
  const location = useLocation();
  const navigate = useNavigate();

  const pathname = location.pathname;
  let element: React.ReactNode = null;
  if (pathname === '/') element = <SystemAccessPage />;
  else if (pathname === '/home') element = <HomePage />;
  else if (pathname === '/request-access') element = <RequestAccessPage />;
  else if (privateRoutes[pathname]) {
    const PrivateComponent = privateRoutes[pathname];
    element = (
      <Suspense fallback={<div style={{ minHeight: '100dvh', background: PAPER }} />}>
        <PrivateComponent />
      </Suspense>
    );
  }

  useEffect(() => {
    if (!element && !PUBLIC_PATHS.includes(pathname)) {
      navigate('/', { replace: true });
    }
  }, [pathname, navigate, element]);

  useEffect(() => {
    const themeColor = pathname === '/' ? OXFORD : PAPER;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', themeColor);
    document.documentElement.style.backgroundColor = themeColor;
    document.body.style.backgroundColor = themeColor;
  }, [pathname]);

  if (element === null) return null;

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={pathname}
        initial={{ opacity: 0, x: 12 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -12 }}
        transition={{ duration: DURATION, ease: EASE }}
        style={{ minHeight: '100dvh' }}
      >
        {element}
      </motion.div>
    </AnimatePresence>
  );
}
