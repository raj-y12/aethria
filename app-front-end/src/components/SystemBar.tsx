import { useState, useEffect } from 'react';
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

const PAPER = 'rgba(242,240,234,1)';
const PAPER_INACTIVE = 'rgba(242,240,234,0.4)';
const STORAGE_KEY = 'aethria_last_activity';

/**
 * Left-side vertical system bar: wordmark, JUDGEMENTS / SYSTEM toggles, clock, nav + logout.
 */
export default function SystemBar({ rightPanel = null, onShowFeed, onShowSystem, onClose, navLink }: SystemBarProps) {
  const [time, setTime] = useState(new Date());
  const [hasEnteredOnce, setHasEnteredOnce] = useState(false);
  const displayName = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('authUser') : null;

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

  const handleLogout = () => {
    try {
      localStorage.removeItem(STORAGE_KEY);
      sessionStorage.removeItem('auth');
      sessionStorage.removeItem('authUser');
    } finally {
      window.location.reload();
    }
  };

  const baseClass =
    'hidden lg:flex fixed top-0 bottom-4 left-4 z-50 flex-col justify-between w-44 bg-oxford border border-white/[0.06]';
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
              duration: 0.8,
              ease: tokens.motion.ease,
            }
      }
    >
      {/* All controls stacked and centered: clock, toggles, user, nav, logout */}
      <div className="flex flex-col items-center gap-4 h-full">
        {/* Clock at the top */}
        <span
          className="tabular-nums font-mono text-[11px] leading-none"
          style={{ color: PAPER_INACTIVE, letterSpacing: '0.08em' }}
          aria-live="polite"
        >
          {formatted}
        </span>

        {/* Mode toggles */}
        <div className="flex flex-col items-center gap-2 mt-1">
          <button
            type="button"
            onClick={rightPanel === 'feed' ? onClose : onShowFeed}
            className="transition-transform duration-200 hover:-translate-y-[1px] hover:opacity-80"
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '10px',
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
              color: rightPanel === 'feed' ? PAPER : PAPER_INACTIVE,
              background: 'none',
              border: 'none',
              borderBottom: rightPanel === 'feed' ? `1px solid ${PAPER}` : '1px solid transparent',
              paddingBottom: rightPanel === 'feed' ? '3px' : 0,
              cursor: 'pointer',
              transition: `color 0.2s ${tokens.motion.easeCss}, border-color 0.2s ${tokens.motion.easeCss}, padding 0.2s ${tokens.motion.easeCss}`,
            }}
            aria-pressed={rightPanel === 'feed'}
          >
            Judgements
          </button>
          <button
            type="button"
            onClick={rightPanel === 'system' ? onClose : onShowSystem}
            className="transition-transform duration-200 hover:-translate-y-[1px] hover:opacity-80"
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '10px',
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
              color: rightPanel === 'system' ? PAPER : PAPER_INACTIVE,
              background: 'none',
              border: 'none',
              borderBottom: rightPanel === 'system' ? `1px solid ${PAPER}` : '1px solid transparent',
              paddingBottom: rightPanel === 'system' ? '3px' : 0,
              cursor: 'pointer',
              transition: `color 0.2s ${tokens.motion.easeCss}, border-color 0.2s ${tokens.motion.easeCss}, padding 0.2s ${tokens.motion.easeCss}`,
            }}
            aria-pressed={rightPanel === 'system'}
          >
            System
          </button>
        </div>

        {/* Nav + username + logout pinned to the bottom of the stack */}
        <div className="mt-auto flex flex-col items-center gap-2">
          {navLink && (
            <a
              href={navLink.href}
              className="font-mono text-[10px] uppercase tracking-[0.16em] text-ivory/70 hover:text-ivory transition-colors"
            >
              {navLink.label}
            </a>
          )}
          {displayName && (
            <span
              style={{
                fontFamily: tokens.font.body,
                fontSize: '11px',
                fontWeight: 400,
                color: 'rgba(242, 240, 234, 0.6)',
              }}
              aria-label={`Signed in as ${displayName}`}
            >
              {displayName}
            </span>
          )}
          <button
            type="button"
            onClick={handleLogout}
            className="font-mono text-[10px] uppercase tracking-[0.16em] text-ivory/50 hover:text-ivory/80 transition-colors"
          >
            Log out
          </button>
        </div>
      </div>
    </motion.header>
  );
}
