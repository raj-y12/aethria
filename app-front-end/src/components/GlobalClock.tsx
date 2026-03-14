import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router';
import { useClerk } from '@clerk/react-router';

/**
 * Central temporal reference. Minimal context; no decoration.
 */
export default function GlobalClock() {
  const navigate = useNavigate();
  const { signOut } = useClerk();
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const formatted = time.toLocaleTimeString('en-GB', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

  const handleLogout = () => {
    localStorage.removeItem('aethria_last_activity');
    signOut?.().then(() => navigate('/sign-in', { replace: true }));
  };

  return (
    <header
      className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 sm:px-8 lg:px-12 pt-6 pb-4 shrink-0"
      style={{ backgroundColor: '#F2F0EA', borderBottom: '1px solid rgba(0, 33, 71, 0.06)' }}
    >
      <Link
        to="/v1"
        className="font-display font-bold text-[17px] text-oxford hover:opacity-80 transition-opacity"
        aria-label="Aethria"
      >
        Aethria
      </Link>
      <div className="absolute left-1/2 -translate-x-1/2 flex items-center gap-2 sm:gap-3">
        <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60">
          Local
        </span>
        <span
          className="font-mono text-oxford text-[12px] sm:text-[13px] tabular-nums"
          aria-live="polite"
        >
          {formatted}
        </span>
      </div>
      <button
        type="button"
        onClick={handleLogout}
        className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60 hover:text-oxford transition-colors duration-300 shrink-0"
      >
        Log out
      </button>
    </header>
  );
}
