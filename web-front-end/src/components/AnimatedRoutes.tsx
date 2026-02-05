import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import SystemAccessPage from './SystemAccessPage';
import HomePage from '../HomePage';
import RequestAccessPage from '../RequestAccessPage';

const DURATION = 0.3;
const EASE = [0.16, 1, 0.3, 1];

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

  if (element === null) return null;

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={pathname}
        initial={{ opacity: 0, x: 12 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -12 }}
        transition={{ duration: DURATION, ease: EASE }}
        style={{ minHeight: '100vh' }}
      >
        {element}
      </motion.div>
    </AnimatePresence>
  );
}
