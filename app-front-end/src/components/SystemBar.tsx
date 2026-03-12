import { useState, useEffect } from 'react';
import { tokens } from '../design-system/tokens';

interface SystemBarProps {
  scoutCount?: number;
  agentConfig?: unknown;
  rightPanel?: 'memo' | 'feed' | 'system' | null;
  onShowFeed?: () => void;
  onShowSystem?: () => void;
  onClose?: () => void;
}

const PAPER = 'rgba(242,240,234,1)';
const PAPER_INACTIVE = 'rgba(242,240,234,0.4)';

/**
 * Status strip: wordmark, JUDGEMENTS / SYSTEM toggles, and clock. Settings / Log out live in the footer.
 */
export default function SystemBar({ rightPanel = null, onShowFeed, onShowSystem, onClose }: SystemBarProps) {
  const [time, setTime] = useState(new Date());
  const displayName = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('authUser') : null;

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

  return (
    <header
      className="fixed top-4 left-4 sm:top-6 sm:left-6 lg:top-8 lg:left-8 right-0 z-50 flex items-center justify-between h-14 px-6 sm:px-8 lg:px-12 bg-oxford border-b border-white/[0.06]"
      style={{ boxShadow: '0 1px 0 0 rgba(255,255,255,0.06)' }}
      aria-label="System"
    >
      <a
        href="/"
        className="font-display font-medium text-[15px] text-ivory hover:opacity-90 transition-opacity tracking-tight flex items-center self-center"
        aria-label="Aethria"
      >
        Aethria
      </a>

      {/* JUDGEMENTS / SYSTEM toggles (32px gap) + 48px + clock flush right */}
      <div className="flex items-center min-h-[2.5rem]" style={{ gap: '48px' }}>
        <div className="flex items-center" style={{ gap: '32px' }}>
          <button
            type="button"
            onClick={rightPanel === 'feed' ? onClose : onShowFeed}
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
        <div className="flex items-center ml-auto gap-4">
          {displayName && (
            <span
              className="font-mono text-[11px] leading-none"
              style={{ color: PAPER, letterSpacing: '0.06em', opacity: 0.9 }}
              aria-label={`Signed in as ${displayName}`}
            >
              {displayName}
            </span>
          )}
          <span
            className="tabular-nums font-mono text-[10px] leading-none"
            style={{ color: PAPER_INACTIVE, letterSpacing: '0.05em' }}
            aria-live="polite"
          >
            {formatted}
          </span>
        </div>
      </div>
    </header>
  );
}
