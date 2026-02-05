import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import SystemAccessPage from './SystemAccessPage';
import HomePage from '../HomePage';
import RequestAccessPage from '../RequestAccessPage';

const DURATION = 0.3;
const EASE: [number, number, number, number] = [0.16, 1, 0.3, 1];
const PAPER = '#F2F0EA';
const OXFORD = '#002147';

export default function AnimatedRoutes() {
  const location = useLocation();
  const navigate = useNavigate();

  const pathname = location.pathname;
  let element: React.ReactNode = null;
  if (pathname === '/') element = <SystemAccessPage />;
  else if (pathname === '/home') element = <HomePage />;
  else if (pathname === '/request-access') element = <RequestAccessPage />;

  useEffect(() => {
    if (pathname !== '/' && pathname !== '/home' && pathname !== '/request-access') {
      navigate('/', { replace: true });
    }
  }, [pathname, navigate]);

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
