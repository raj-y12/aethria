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
  variant?: 'fixed' | 'embedded';
  onShowDeals?: () => void;
  onShowFeed?: () => void;
  onShowSystem?: () => void;
  onClose?: () => void;
  navLink?: { href: string; label: string };
}

/** Thin horizontal rule — only used in fixed (full-height) variant. */
function SpineRule() {
  return (
    <div
      className="w-full max-w-[6rem] mx-auto h-px bg-white/[0.07]"
      aria-hidden
    />
  );
}

function SpineNavButton({
  label,
  active,
  onClick,
  ariaPressed,
  shortcut,
  compact,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  ariaPressed: boolean;
  shortcut?: string;
  compact?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={shortcut ? `${label} (${shortcut})` : label}
      className={`type-meta w-full flex items-center justify-start px-2 cursor-pointer tracking-[0.06em] btn-interaction transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35 ${
        active ? 'text-white' : 'text-white/55 hover:text-white/88'
      } ${compact ? 'min-h-[32px]' : 'min-h-[44px]'}`}
      style={{ transitionTimingFunction: 'var(--motion-ease)' }}
      aria-pressed={ariaPressed}
      aria-current={active ? 'page' : undefined}
    >
      <span
        className={`inline-block px-2 py-1 transition-[background-color,color] ${
          active ? 'bg-white/[0.08]' : 'hover:bg-white/[0.05]'
        }`}
      >
        {label}
      </span>
    </button>
  );
}

export default function SystemBar({
  rightPanel = null,
  variant = 'fixed',
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
  const [agentActionPending, setAgentActionPending] = useState(false);
  const [agentActionError, setAgentActionError] = useState<string | null>(null);

  const doLogout = () => {
    localStorage.removeItem('aethria_last_activity');
    signOut?.().then(() => navigate('/sign-in', { replace: true }));
  };

  const toggleAgentsAndLogout = async (enabled: boolean) => {
    setAgentActionPending(true);
    setAgentActionError(null);
    try {
      await toggleAgents(enabled);
      doLogout();
    } catch {
      setAgentActionError('Unable to update agent state. Please retry.');
    } finally {
      setAgentActionPending(false);
    }
  };

  useEffect(() => {
    const tick = () => setTime(new Date());
    tick();
    const t = setInterval(tick, 60_000);
    return () => clearInterval(t);
  }, []);

  const workspaceChrome =
    onShowDeals != null && onShowFeed != null && onShowSystem != null && onClose != null;

  useEffect(() => {
    if (!workspaceChrome) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      const tagName = target?.tagName?.toLowerCase();
      if (
        target?.isContentEditable ||
        tagName === 'input' ||
        tagName === 'textarea' ||
        tagName === 'select'
      ) return;

      if (event.key === '1') {
        event.preventDefault();
        onShowDeals?.();
      } else if (event.key === '2') {
        event.preventDefault();
        if (rightPanel === 'feed') onClose?.();
        else onShowFeed?.();
      } else if (event.key === '3') {
        event.preventDefault();
        if (rightPanel === 'system') onClose?.();
        else onShowSystem?.();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [workspaceChrome, onShowDeals, onShowFeed, onShowSystem, onClose, rightPanel]);

  useEffect(() => {
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
    .toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
    .toUpperCase();

  const isEmbedded = variant === 'embedded';

  // ── Embedded variant ──────────────────────────────────────────────────────
  // Compact card inside the left aside column. No entrance animation needed.
  if (isEmbedded) {
    return (
      <>
        <div
          className="hidden lg:flex flex-col h-full w-full bg-oxford border border-white/[0.08] overflow-hidden"
          style={{ padding: '14px 14px 12px' }}
          aria-label="System"
        >
          {/* Top: wordmark + time */}
          <div className="flex items-baseline justify-between gap-2 shrink-0 px-1">
            <p className="font-wordmark font-normal text-[14px] leading-none tracking-[0.01em] text-white/75">
              Aethria
            </p>
            <span className="type-meta tabular-nums leading-none text-white/40">
              {timeShort}
            </span>
          </div>

          {/* Account */}
          <div className="mt-phi-3 shrink-0 px-1">
            <span
              className="type-meta truncate max-w-full text-white/50 block"
              title={displayName}
            >
              {displayName}
            </span>
          </div>

          {/* Nav — workspace chrome only */}
          {workspaceChrome ? (
            <div className="mt-phi-3 flex flex-col gap-0.5 w-full shrink-0">
              <SpineNavButton
                label="Deals"
                active={rightPanel !== 'system' && rightPanel !== 'feed'}
                ariaPressed={rightPanel !== 'system' && rightPanel !== 'feed'}
                onClick={() => onShowDeals!()}
                shortcut="1"
                compact
              />
              <SpineNavButton
                label="Signals"
                active={rightPanel === 'feed'}
                ariaPressed={rightPanel === 'feed'}
                onClick={() => (rightPanel === 'feed' ? onClose!() : onShowFeed!())}
                shortcut="2"
                compact
              />
              <SpineNavButton
                label="System"
                active={rightPanel === 'system'}
                ariaPressed={rightPanel === 'system'}
                onClick={() => (rightPanel === 'system' ? onClose!() : onShowSystem!())}
                shortcut="3"
                compact
              />
            </div>
          ) : null}

          {/* Bottom: settings + logout */}
          <div className="mt-auto pt-phi-3 flex flex-col gap-phi-2 shrink-0 px-1">
            {navLink ? (
              <Link
                to={navLink.href}
                className="type-meta text-white/45 hover:text-white/80 btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
              >
                {navLink.label}
              </Link>
            ) : null}
            {agentActionError ? (
              <p className="type-meta text-white/65" role="status" aria-live="polite">
                {agentActionError}
              </p>
            ) : null}
            <button
              type="button"
              onClick={() => setShowLogoutModal(true)}
              disabled={agentActionPending}
              className="type-meta text-left text-white/40 hover:text-white/75 bg-transparent border-0 p-0 cursor-pointer btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35 disabled:opacity-60"
            >
              {agentActionPending ? 'Updating…' : 'Log out'}
            </button>
          </div>
        </div>

        <AgentLogoutModal
          open={showLogoutModal}
          agentsEnabled={agentsEnabled}
          onCancel={() => setShowLogoutModal(false)}
          onKeepRunning={() => { setShowLogoutModal(false); doLogout(); }}
          onTurnOffAndLogout={async () => { await toggleAgentsAndLogout(false); }}
          onTurnOnAndStay={async () => { await toggleAgentsAndLogout(true); }}
        />
      </>
    );
  }

  // ── Fixed variant ─────────────────────────────────────────────────────────
  // Full-height left sidebar (used by SettingsPage).
  return (
    <>
      <motion.header
        className="hidden md:flex fixed top-0 bottom-0 left-0 z-50 flex-col justify-between w-36 lg:w-40 bg-oxford"
        style={{ padding: '26px 16px 20px' }}
        aria-label="System"
        initial={
          hasEnteredOnce
            ? undefined
            : reduceMotion
              ? { y: 0, opacity: 1 }
              : { y: -80, opacity: 0 }
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
        <div className="flex flex-col gap-5 h-full min-h-0">
          {/* Wordmark */}
          <div className="shrink-0 px-3">
            <p className="font-wordmark font-normal text-[16px] leading-none tracking-[0.01em] text-white/80">
              Aethria
            </p>
          </div>

          <SpineRule />

          {/* Time + date */}
          <div className="shrink-0 px-3 flex flex-col gap-2" aria-live="polite">
            <span className="type-meta tabular-nums leading-none text-white/55">{timeShort}</span>
            <span className="type-meta leading-tight tracking-[0.08em] text-white/30">{dateShort}</span>
          </div>

          <SpineRule />

          {/* Account */}
          <div className="w-full flex flex-col gap-3 shrink-0 px-3">
            <span className="type-meta truncate max-w-full text-white/70" title={displayName}>
              {displayName}
            </span>
            {navLink ? (
              <Link
                to={navLink.href}
                className="type-meta inline-flex min-h-[44px] items-center text-white/65 hover:text-white btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
              >
                {navLink.label}
              </Link>
            ) : null}
          </div>

          {/* Log out */}
          <div className="mt-auto flex flex-col gap-3 pt-2 shrink-0 px-3">
            {agentActionError ? (
              <p className="type-meta text-white/75" role="status" aria-live="polite">
                {agentActionError}
              </p>
            ) : null}
            <button
              type="button"
              onClick={() => setShowLogoutModal(true)}
              disabled={agentActionPending}
              className="type-meta inline-flex min-h-[44px] items-center tracking-[0.06em] text-white/60 hover:text-white bg-transparent border-0 p-0 cursor-pointer btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35 disabled:opacity-60"
            >
              {agentActionPending ? 'Updating…' : 'Log out'}
            </button>
          </div>
        </div>
      </motion.header>

      <AgentLogoutModal
        open={showLogoutModal}
        agentsEnabled={agentsEnabled}
        onCancel={() => setShowLogoutModal(false)}
        onKeepRunning={() => { setShowLogoutModal(false); doLogout(); }}
        onTurnOffAndLogout={async () => { await toggleAgentsAndLogout(false); }}
        onTurnOnAndStay={async () => { await toggleAgentsAndLogout(true); }}
      />
    </>
  );
}
