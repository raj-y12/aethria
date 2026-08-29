import { Suspense, lazy, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import HomePage from '../HomePage';
import TeamPage from '../TeamPage';

const DURATION = 0.3;
const EASE: [number, number, number, number] = [0.16, 1, 0.3, 1];
const PAPER = '#D9D7D4';

// ponytail: module-scope flag, not state — first client render must match SSG (no animation),
// later route changes (post-mount) should still animate.
let animateEntrances = false;

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

const PUBLIC_PATHS = ['/', '/home', '/team'];

export default function AnimatedRoutes() {
  const location = useLocation();
  const navigate = useNavigate();

  const pathname = location.pathname;

  let element: React.ReactNode = null;
  if (pathname === '/' || pathname === '/home') element = <HomePage />;
  else if (pathname === '/team') element = <TeamPage />;
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
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', PAPER);
    document.documentElement.style.backgroundColor = PAPER;
    document.body.style.backgroundColor = PAPER;
  }, []);

  useEffect(() => {
    if (location.hash) return;

    const lenis = (
      window as unknown as {
        __lenis?: {
          scrollTo: (target: number, options?: { immediate?: boolean }) => void;
        };
      }
    ).__lenis;

    if (lenis) {
      lenis.scrollTo(0, { immediate: true });
      return;
    }

    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  }, [pathname, location.hash]);

  useEffect(() => {
    animateEntrances = true;
  }, []);

  if (element === null) return null;

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={pathname}
        initial={animateEntrances ? { opacity: 0, x: 12 } : false}
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
