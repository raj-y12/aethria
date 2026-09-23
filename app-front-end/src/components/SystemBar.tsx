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

export function WorkspaceGlyph({ label }: { label: string }) {
  const kind = label.toLowerCase();
  return (
    <svg className="aethria-nav-glyph" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      {kind === 'home' ? <path d="M3 8.2 9 3l6 5.2v6.3H3V8.2Z M6.5 14.5v-3.7h5v3.7" /> : null}
      {kind === 'flow' ? <path d="M3 4.5h12M3 9h8M3 13.5h12" /> : null}
      {kind === 'portfolio' ? <path d="M3 5.5h12v9H3zM6 5.5V3.8h6v1.7M6.5 9h5" /> : null}
      {kind === 'fund' ? <path d="M3 14.5V8m4 6.5V4m4 10.5v-8m4 8V2.5" /> : null}
      {kind === 'dispatch' ? <path d="m3 9 12-5-3.8 10-2.2-4-4-1Zm6 1 3.2-3.2" /> : null}
      {kind === 'logout' ? <path d="M7 3.5H4.5v11H7M9 9h5.5M12 6.5 14.5 9 12 11.5" /> : null}
      {kind === 'settings' ? <path d="m9 2.7 1 .5.3 1.2 1 .6 1.2-.2.8.8-.2 1.2.6 1 .9.7v1.1l-.9.7-.6 1 .2 1.2-.8.8-1.2-.2-1 .6-.3 1.2-1 .5-1-.5-.3-1.2-1-.6-1.2.2-.8-.8.2-1.2-.6-1-.9-.7V8.5l.9-.7.6-1-.2-1.2.8-.8 1.2.2 1-.6.3-1.2 1-.5Z M9 7a2 2 0 1 0 0 4 2 2 0 0 0 0-4Z" /> : null}
      {kind !== 'home' && kind !== 'flow' && kind !== 'portfolio' && kind !== 'fund' && kind !== 'dispatch' && kind !== 'logout' && kind !== 'settings' ? (
        <circle cx="9" cy="9" r="5.5" />
      ) : null}
    </svg>
  );
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

export function SpineNavButton({
  label,
  active,
  onClick,
  ariaPressed,
  shortcut,
  compact,
  surface = 'oxford',
  running = false,
  indicatorId,
  className = '',
  motionIndex,
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
  className?: string;
  motionIndex?: number;
  /**
   * Shared layout id for a sliding active background. Buttons in the same nav
   * that pass the same id hand the highlight between them with a glide instead
   * of a blink. Omit to keep the static background.
  */
  indicatorId?: string;
}) {
  const reduceMotion = usePrefersReducedMotion();
  const onPaper = surface === 'paper';
  // On oxford, .type-action-inverse pins the button color at paper/72 with
  // class-level specificity (idle white/60 intentionally loses to it), so the
  // active state needs !important to hold full white. On paper the inverse
  // class must be omitted entirely or it paints cream text on cream.
  const textActive = onPaper ? 'text-oxford' : '!text-white';
  const textIdle = onPaper ? 'text-oxford/65 hover:text-oxford/80' : 'text-white/60 hover:text-white/[0.88]';
  const ring = onPaper ? 'focus-visible:ring-oxford/35' : 'focus-visible:ring-white/35';
  const bgActive = onPaper ? 'bg-surface-selected' : 'bg-white/[0.08]';
  const bgHover = onPaper ? 'hover:bg-oxford/[0.04]' : 'hover:bg-white/[0.05]';
  const shortcutActive = onPaper ? 'text-oxford' : 'text-white';
  const shortcutIdle = onPaper
    ? 'text-oxford/65 group-hover:text-oxford'
    : 'text-white/60 group-hover:text-white';
  const entryDelay = motionIndex == null ? 0 : motionIndex * 0.04;
  const navVariants = {
    hidden: reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 5 },
    visible: {
      opacity: 1,
      y: 0,
      transition: transitionOrReduced(reduceMotion, {
        duration: tokens.motion.duration.short,
        ease: tokens.motion.ease,
        delay: entryDelay,
      }),
    },
    exit: reduceMotion
      ? { opacity: 1, y: 0 }
      : {
          opacity: 0,
          y: 5,
          transition: {
            duration: tokens.motion.duration.micro,
            ease: tokens.motion.ease,
          },
        },
  };

  return (
    <motion.button
      type="button"
      onClick={onClick}
      title={shortcut ? `${label} (${shortcut})` : label}
      data-nav-label={label}
      className={`aethria-spine-nav-button type-action ${onPaper ? '' : 'type-action-inverse '}group relative w-full flex items-center justify-between gap-phi-3 cursor-pointer btn-interaction btn-interaction--no-press transition-colors focus-visible:outline-none focus-visible:ring-2 ${ring} ${
        active ? `${textActive} ${indicatorId ? '' : bgActive}` : `${textIdle} ${bgHover}`
      } ${compact ? 'min-h-[32px] px-phi-4 py-phi-1' : 'min-h-[44px] px-2 py-1'} ${className}`}
      style={{ transitionTimingFunction: 'var(--motion-ease)' }}
      aria-pressed={ariaPressed}
      aria-current={active ? 'page' : undefined}
      variants={navVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
      whileTap={reduceMotion ? undefined : { scale: 0.97 }}
      transition={transitionOrReduced(reduceMotion, {
        duration: tokens.motion.duration.micro,
        ease: tokens.motion.ease,
      })}
    >
      {active && indicatorId ? (
        <motion.span
          layoutId={indicatorId}
          className={`absolute inset-0 rounded-[inherit] ${bgActive}`}
          transition={reduceMotion ? { duration: 0 } : { duration: 0.3, ease: tokens.motion.easeInOut }}
          aria-hidden
        />
      ) : null}
      <span className="relative inline-flex min-w-0 items-center gap-phi-2">
        <WorkspaceGlyph label={label} />
        {running ? (
          <span
            className={`h-1.5 w-1.5 shrink-0 rounded-none signal-dot-breathe ${onPaper ? 'bg-oxford' : 'bg-white'}`}
            aria-hidden
          />
        ) : null}
        <span className="aethria-nav-label truncate">{label}</span>
      </span>
      {shortcut ? (
        <span
          className={`relative tabular-nums transition-colors ${active ? shortcutActive : shortcutIdle}`}
          aria-hidden
        >
          {shortcutKeyToRomanNumeral(shortcut)}
        </span>
      ) : null}
    </motion.button>
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
        {/* Nav — workspace chrome only (wordmark + pipeline + clock live in the host rail) */}
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
            <p className="font-wordmark font-medium text-[16px] leading-none tracking-[0.01em] text-paper">
              Aethria<span className="wordmark-dot wordmark-dot--inverse">.</span>
            </p>
          </div>

          <SpineRule />

          {/* Time + date */}
          <div className="shrink-0 px-3 flex flex-col gap-2" aria-live="polite">
            <span className="type-meta type-meta-inverse tabular-nums leading-none">{timeShort}</span>
            <span className="type-label-section type-label-inverse">{dateShort}</span>
          </div>

          <SpineRule />

          {/* Account */}
          <div className="w-full flex flex-col gap-3 shrink-0 px-3">
            <span className="type-meta type-meta-inverse truncate max-w-full" title={displayName}>
              {displayName}
            </span>
            {navLink ? (
              <Link
                to={navLink.href}
                className="type-action type-action-inverse inline-flex min-h-[44px] items-center hover:text-white btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
              >
                {navLink.label}
              </Link>
            ) : null}
          </div>

          {/* Log out */}
          <div className="mt-auto flex flex-col gap-3 pt-2 shrink-0 px-3">
            {agentActionError ? (
              <p className="type-status type-status-inverse" role="status" aria-live="polite">
                {agentActionError}
              </p>
            ) : null}
            <button
              type="button"
              onClick={requestLogout}
              disabled={agentActionPending}
              className="type-action type-action-inverse hover:text-white inline-flex min-h-[44px] items-center bg-transparent border-0 p-0 cursor-pointer btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35 disabled:opacity-60"
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
