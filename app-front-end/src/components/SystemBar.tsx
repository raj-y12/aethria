import { useState, useEffect } from 'react';
import { Link } from 'react-router';
import { motion } from 'framer-motion';
import { tokens } from '../design-system/tokens';
import { transitionOrReduced } from '../design-system/motion';
import { usePrefersReducedMotion } from '../hooks';
import { useAgentLogoutFlow } from '../hooks/useAgentLogoutFlow';
import AgentLogoutModal from './AgentLogoutModal';

interface SystemBarProps {
  agentConfig?: unknown;
  rightPanel?: 'feed' | 'system' | null;
  variant?: 'fixed' | 'embedded';
  onShowDeals?: () => void;
  onShowFeed?: () => void;
  onShowSystem?: () => void;
  onClose?: () => void;
  /** Opens the full-screen dispatch (company lookup) takeover. */
  onDispatch?: () => void;
  /** True while a background lookup is running — shows a breathing dot on Dispatch. */
  dispatchActive?: boolean;
  navLink?: { href: string; label: string };
}

/** Spine nav shortcut badges — Roman numerals for keys 1–12 (workspace panel shortcuts). */
function shortcutKeyToRomanNumeral(shortcut: string): string {
  const n = parseInt(shortcut.trim(), 10);
  if (!Number.isFinite(n) || n < 1 || n > 12) return shortcut.trim();
  const romans = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII'];
  return romans[n] ?? shortcut.trim();
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
  surface = 'oxford',
  running = false,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  ariaPressed: boolean;
  shortcut?: string;
  compact?: boolean;
  surface?: 'oxford' | 'paper';
  /** Shows a breathing dot before the label (e.g. a lookup running in the background). */
  running?: boolean;
}) {
  const onPaper = surface === 'paper';
  const textActive = onPaper ? 'text-oxford' : 'text-white';
  const textIdle = onPaper ? 'text-oxford/50 hover:text-oxford/80' : 'text-white/55 hover:text-white/88';
  const ring = onPaper ? 'focus-visible:ring-oxford/35' : 'focus-visible:ring-white/35';
  const bgActive = onPaper ? 'bg-surface-selected' : 'bg-white/[0.08]';
  const bgHover = onPaper ? 'hover:bg-oxford/[0.04]' : 'hover:bg-white/[0.05]';
  const shortcutActive = onPaper ? 'text-oxford/60' : 'text-white/75';
  const shortcutIdle = onPaper
    ? 'text-oxford/25 group-hover:text-oxford/45'
    : 'text-white/30 group-hover:text-white/52';

  return (
    <button
      type="button"
      onClick={onClick}
      title={shortcut ? `${label} (${shortcut})` : label}
      className={`group type-label-tab w-full flex items-center justify-between gap-phi-3 cursor-pointer btn-interaction btn-interaction--no-press transition-colors focus-visible:outline-none focus-visible:ring-2 ${ring} ${
        active ? `${textActive} ${bgActive}` : `${textIdle} ${bgHover}`
      } ${compact ? 'min-h-[32px] px-phi-4 py-phi-1' : 'min-h-[44px] px-2 py-1'}`}
      style={{ transitionTimingFunction: 'var(--motion-ease)' }}
      aria-pressed={ariaPressed}
      aria-current={active ? 'page' : undefined}
    >
      <span className="inline-flex min-w-0 items-center gap-phi-2">
        {running ? (
          <span
            className={`h-1.5 w-1.5 shrink-0 rounded-none signal-dot-breathe ${onPaper ? 'bg-oxford' : 'bg-white'}`}
            aria-hidden
          />
        ) : null}
        <span className="truncate">{label}</span>
      </span>
      {shortcut ? (
        <span
          className={`tabular-nums transition-colors ${active ? shortcutActive : shortcutIdle}`}
          aria-hidden
        >
          {shortcutKeyToRomanNumeral(shortcut)}
        </span>
      ) : null}
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
  onDispatch,
  dispatchActive = false,
  navLink,
}: SystemBarProps) {
  const reduceMotion = usePrefersReducedMotion();
  const {
    displayName,
    agentActionPending,
    agentActionError,
    requestLogout,
    logoutModalProps,
  } = useAgentLogoutFlow();
  const [time, setTime] = useState(new Date());
  const [hasEnteredOnce, setHasEnteredOnce] = useState(false);

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
      <div
        className="hidden lg:flex flex-col h-auto w-full min-h-0 bg-transparent overflow-visible"
        aria-label="System"
      >
        {/* Nav — workspace chrome only (wordmark + pipeline + clock live in MainLayout above) */}
        {workspaceChrome ? (
          <div className="flex flex-col gap-0.5 w-full shrink-0">
              <SpineNavButton
                label="Workspace"
                active={rightPanel !== 'system' && rightPanel !== 'feed'}
                ariaPressed={rightPanel !== 'system' && rightPanel !== 'feed'}
                onClick={() => onShowDeals!()}
                shortcut="1"
                compact
                surface="paper"
              />
              <SpineNavButton
                label="Judgements"
                active={rightPanel === 'feed'}
                ariaPressed={rightPanel === 'feed'}
                onClick={() => (rightPanel === 'feed' ? onClose!() : onShowFeed!())}
                shortcut="2"
                compact
                surface="paper"
              />
              <SpineNavButton
                label="System"
                active={rightPanel === 'system'}
                ariaPressed={rightPanel === 'system'}
                onClick={() => (rightPanel === 'system' ? onClose!() : onShowSystem!())}
                shortcut="3"
                compact
                surface="paper"
              />
              {onDispatch ? (
                <SpineNavButton
                  label="Dispatch"
                  active={false}
                  ariaPressed={false}
                  onClick={() => onDispatch()}
                  shortcut="⌘K"
                  compact
                  surface="paper"
                  running={dispatchActive}
                />
              ) : null}
          </div>
        ) : null}
      </div>
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
            <p className="font-wordmark font-medium text-[16px] leading-none tracking-[0.01em] text-white/80">
              Aethria
            </p>
          </div>

          <SpineRule />

          {/* Time + date */}
          <div className="shrink-0 px-3 flex flex-col gap-2" aria-live="polite">
            <span className="type-meta tabular-nums leading-none text-white/55">{timeShort}</span>
            <span className="type-label-section text-white/30">{dateShort}</span>
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
              onClick={requestLogout}
              disabled={agentActionPending}
              className="type-label-tab text-white/60 hover:text-white inline-flex min-h-[44px] items-center bg-transparent border-0 p-0 cursor-pointer btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35 disabled:opacity-60"
            >
              {agentActionPending ? 'Updating...' : 'Log out'}
            </button>
          </div>
        </div>
      </motion.header>

      <AgentLogoutModal {...logoutModalProps} />
    </>
  );
}
