import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router';
import { useUser, useClerk } from '@clerk/react';
import { motion } from 'framer-motion';
import { tokens } from '../design-system/tokens';

interface SystemBarProps {
  scoutCount?: number;
  agentConfig?: unknown;
  rightPanel?: 'memo' | 'feed' | 'system' | null;
  onShowFeed?: () => void;
  onShowSystem?: () => void;
  onClose?: () => void;
  navLink?: { href: string; label: string };
}

/**
 * Left-side vertical system bar: clock (top), username, JUDGEMENTS / SYSTEM toggles, nav + logout.
 */
export default function SystemBar({ rightPanel = null, onShowFeed, onShowSystem, onClose, navLink }: SystemBarProps) {
  const navigate = useNavigate();
  const { user } = useUser();
  const { signOut } = useClerk();
  const [time, setTime] = useState(new Date());
  const displayName = user?.username ?? user?.primaryEmailAddress?.emailAddress ?? 'Account';
  const [hasEnteredOnce, setHasEnteredOnce] = useState(false);

  const handleLogout = () => {
    localStorage.removeItem('aethria_last_activity');
    signOut?.().then(() => navigate('/sign-in', { replace: true }));
  };

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    // One-time entrance "swoop" when the bar first appears after login.
    if (typeof window === 'undefined') return;
    const key = 'aethria_systembar_entered';
    if (sessionStorage.getItem(key) === '1') {
      setHasEnteredOnce(true);
      return;
    }
    sessionStorage.setItem(key, '1');
  }, []);

  const formatted = time.toLocaleTimeString('en-GB', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

  const baseClass =
    'hidden lg:flex fixed top-0 bottom-4 left-4 z-50 flex-col justify-between w-36 bg-oxford border border-white/[0.06]';
  const baseStyle = { boxShadow: '0 1px 0 0 rgba(255,255,255,0.06)', padding: '20px 16px 16px' };

  return (
    <motion.header
      className={baseClass}
      style={baseStyle}
      aria-label="System"
      initial={hasEnteredOnce ? undefined : { y: -80, opacity: 0 }}
      animate={hasEnteredOnce ? undefined : { y: 0, opacity: 1 }}
      transition={
        hasEnteredOnce
          ? undefined
          : {
              duration: tokens.motion.duration.long,
              ease: tokens.motion.ease,
            }
      }
    >
      {/* All controls stacked: clock (top), username, toggles, nav + logout */}
      <div className="flex flex-col items-center gap-4 h-full">
        {/* Clock at top */}
        <span
          className="type-meta tabular-nums leading-[1.5] text-white/40"
          aria-live="polite"
        >
          {formatted}
        </span>

        {/* Username (account/settings moved to app Settings later) */}
        <div className="w-full flex items-center justify-center min-h-[2.5rem]">
          <span
            className="type-label-tab truncate max-w-full text-center text-white/40"
            title={displayName}
          >
            {displayName}
          </span>
        </div>

        {/* Mode toggles: Judgements / System */}
        <div className="flex flex-col items-center gap-0.5 mt-1 w-full">
          <button
            type="button"
            onClick={rightPanel === 'feed' ? onClose : onShowFeed}
            className={`type-label-tab min-h-[36px] w-full flex items-center justify-center cursor-pointer btn-interaction ${
              rightPanel === 'feed' ? 'text-white' : 'text-white/60 hover:text-white'
            }`}
            style={{ transitionTimingFunction: 'var(--motion-ease)' }}
            aria-pressed={rightPanel === 'feed'}
          >
            <span
              className={`inline-block pb-0.5 ${rightPanel === 'feed' ? 'border-b-2 border-white' : ''}`}
            >
              Judgements
            </span>
          </button>
          <button
            type="button"
            onClick={rightPanel === 'system' ? onClose : onShowSystem}
            className={`type-label-tab min-h-[36px] w-full flex items-center justify-center cursor-pointer btn-interaction ${
              rightPanel === 'system' ? 'text-white' : 'text-white/60 hover:text-white'
            }`}
            style={{ transitionTimingFunction: 'var(--motion-ease)' }}
            aria-pressed={rightPanel === 'system'}
          >
            <span
              className={`inline-block pb-0.5 ${rightPanel === 'system' ? 'border-b-2 border-white' : ''}`}
            >
              System
            </span>
          </button>
        </div>

        {/* Nav + Log out pinned to the bottom of the spine */}
        <div className="mt-auto flex flex-col items-center gap-2">
          {navLink && (
            <a
              href={navLink.href}
              className="type-label-section text-white/70 hover:text-white btn-interaction"
            >
              {navLink.label}
            </a>
          )}
          <button
            type="button"
            onClick={handleLogout}
            className="type-label-tab text-white/40 hover:text-white bg-transparent border-0 p-0 cursor-pointer btn-interaction"
          >
            Log out
          </button>
        </div>
      </div>
    </motion.header>
  );
}
