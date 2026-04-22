import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router';
import { useUser, useClerk } from '@clerk/react';
import { motion } from 'framer-motion';
import { tokens } from '../design-system/tokens';
import { transitionOrReduced } from '../design-system/motion';
import { usePrefersReducedMotion } from '../hooks';
import { useAgentsEnabled } from '../hooks/useAgentsEnabled';
import AgentLogoutModal from './AgentLogoutModal';
import { toggleAgents } from '../api/agents';

interface SystemBarProps {
  agentConfig?: unknown;
  rightPanel?: 'memo' | 'feed' | 'system' | null;
  /** Show work grid (left column); clears System when open. */
  onShowDeals?: () => void;
  onShowFeed?: () => void;
  onShowSystem?: () => void;
  onClose?: () => void;
  navLink?: { href: string; label: string };
}

function SpineRule() {
  return <div className="w-full max-w-[5.5rem] mx-auto h-px bg-white/[0.08]" aria-hidden />;
}

/** Spine controls keep >=44px touch target and clear focus states. */
function SpineNavButton({
  label,
  active,
  onClick,
  ariaPressed,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  ariaPressed: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`type-meta w-full min-h-[44px] flex items-center justify-center cursor-pointer tracking-[0.1em] btn-interaction transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35 ${
        active ? 'text-white' : 'text-white/55 hover:text-white/80'
      }`}
      style={{ transitionTimingFunction: 'var(--motion-ease)' }}
      aria-pressed={ariaPressed}
    >
      {/* Underline always present — full-white when active, dim when inactive */}
      <span
        className={`inline-block pb-0.5 border-b transition-[border-color,color] ${
          active ? 'border-white' : 'border-transparent hover:border-white/50'
        }`}
      >
        {label}
      </span>
    </button>
  );
}

/**
 * Left-side vertical system bar: time + date, identity, nav (Home/Settings), mode toggles, logout.
 */
export default function SystemBar({
  rightPanel = null,
  onShowDeals,
  onShowFeed,
  onShowSystem,
  onClose,
  navLink,
}: SystemBarProps) {
  const reduceMotion = usePrefersReducedMotion();
  const navigate = useNavigate();
  const { user } = useUser();
  const { signOut } = useClerk();
  const agentsEnabled = useAgentsEnabled();
  const [time, setTime] = useState(new Date());
  const displayName = user?.username ?? user?.primaryEmailAddress?.emailAddress ?? 'Account';
  const [hasEnteredOnce, setHasEnteredOnce] = useState(false);
  const [showLogoutModal, setShowLogoutModal] = useState(false);

  const doLogout = () => {
    localStorage.removeItem('aethria_last_activity');
    signOut?.().then(() => navigate('/sign-in', { replace: true }));
  };

  const handleLogout = () => {
    setShowLogoutModal(true);
  };

  const handleTurnOffAndLogout = async () => {
    await toggleAgents(false);
    doLogout();
  };

  const handleTurnOnAndStay = async () => {
    await toggleAgents(true);
    doLogout();
  };

  useEffect(() => {
    const tick = () => setTime(new Date());
    tick();
    const t = setInterval(tick, 60_000);
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

  const timeShort = time.toLocaleTimeString('en-GB', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
  });
  const dateShort = time
    .toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
    })
    .toUpperCase();

  const workspaceChrome =
    onShowDeals != null && onShowFeed != null && onShowSystem != null && onClose != null;

  const baseClass =
    'hidden lg:flex fixed top-0 bottom-0 left-0 z-50 flex-col justify-between w-36 bg-oxford border-r border-r-white/[0.07]';
  const baseStyle = { padding: '24px 18px 20px' };

  return (<>
    <motion.header
      className={baseClass}
      style={baseStyle}
      aria-label="System"
      initial={
        hasEnteredOnce ? undefined : reduceMotion ? { y: 0, opacity: 1 } : { y: -80, opacity: 0 }
      }
      animate={hasEnteredOnce ? undefined : { y: 0, opacity: 1 }}
      transition={
        hasEnteredOnce
          ? undefined
          : transitionOrReduced(reduceMotion, {
              duration: tokens.motion.duration.long,
              ease: tokens.motion.ease,
            })
      }
    >
      <div className="flex flex-col items-center gap-4 h-full min-h-0">
        {/* Wordmark */}
        <div className="shrink-0 text-center">
          <p className="font-wordmark font-normal text-[15px] leading-none tracking-[0.02em] text-white/65">
            Aethria
          </p>
        </div>

        <SpineRule />

        {/* Time + date — updates each minute; same 10px mono as rest of spine */}
        <div className="flex flex-col items-center gap-1 shrink-0" aria-live="polite">
          <span className="type-meta tabular-nums leading-none text-white/55">{timeShort}</span>
          <span className="type-meta leading-tight tracking-[0.14em] uppercase text-white/30">
            {dateShort}
          </span>
        </div>

        <SpineRule />

        {/* Account */}
        <div className="w-full flex flex-col items-center gap-2 shrink-0">
          <span
            className="type-meta truncate max-w-full text-center tracking-[0.1em] text-white/60"
            title={displayName}
          >
            {displayName}
          </span>
          {navLink ? (
            <div className="flex flex-col items-center gap-1 w-full px-0.5">
              <Link
                to={navLink.href}
                className="type-meta inline-flex min-h-[44px] items-center justify-center text-center leading-[1.4] tracking-[0.1em] text-white/65 hover:text-white btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
              >
                {navLink.label}
              </Link>
            </div>
          ) : null}
        </div>

        <SpineRule />

        {workspaceChrome ? (
          <>
            <div className="flex flex-col items-center gap-0.5 w-full shrink-0">
              <SpineNavButton
                label="Judgements"
                active={rightPanel === 'feed'}
                ariaPressed={rightPanel === 'feed'}
                onClick={() => (rightPanel === 'feed' ? onClose!() : onShowFeed!())}
              />
              <SpineNavButton
                label="Deals"
                active={rightPanel !== 'system' && rightPanel !== 'feed'}
                ariaPressed={rightPanel !== 'system' && rightPanel !== 'feed'}
                onClick={() => onShowDeals!()}
              />
              <SpineNavButton
                label="System"
                active={rightPanel === 'system'}
                ariaPressed={rightPanel === 'system'}
                onClick={() => (rightPanel === 'system' ? onClose!() : onShowSystem!())}
              />
            </div>
            <SpineRule />
          </>
        ) : null}

        {/* Log out */}
        <div className="mt-auto flex flex-col items-center gap-2 pt-1 shrink-0">
          <button
            type="button"
            onClick={handleLogout}
            className="type-meta inline-flex min-h-[44px] items-center tracking-[0.1em] text-white/60 hover:text-white bg-transparent border-0 p-0 cursor-pointer btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
          >
            Log out
          </button>
        </div>
      </div>
    </motion.header>

    {/* Agent logout modal — rendered outside the bar via portal */}
    <AgentLogoutModal
      open={showLogoutModal}
      agentsEnabled={agentsEnabled}
      onCancel={() => setShowLogoutModal(false)}
      onKeepRunning={() => {
        setShowLogoutModal(false);
        doLogout();
      }}
      onTurnOffAndLogout={handleTurnOffAndLogout}
      onTurnOnAndStay={handleTurnOnAndStay}
    />
  </>);
}
