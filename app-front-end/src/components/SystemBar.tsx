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
  rightPanel?: 'memo' | 'feed' | 'system' | null;
  variant?: 'fixed' | 'embedded';
  onShowDeals?: () => void;
  onShowFeed?: () => void;
  onShowSystem?: () => void;
  onClose?: () => void;
  navLink?: { href: string; label: string };
  /** Desktop embedded rail: pipeline health line (moved from Live overview). */
  pipelineState?: 'On' | 'Off' | 'Issue';
  pipelineIssueHelpOpen?: boolean;
  onPipelineIssueHelpToggle?: () => void;
  onPipelineOpenSettings?: () => void;
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
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  ariaPressed: boolean;
  shortcut?: string;
  compact?: boolean;
  surface?: 'oxford' | 'paper';
}) {
  const onPaper = surface === 'paper';
  const textActive = onPaper ? 'text-oxford' : 'text-white';
  const textIdle = onPaper ? 'text-oxford/55 hover:text-oxford' : 'text-white/55 hover:text-white/88';
  const ring = onPaper ? 'focus-visible:ring-oxford/35' : 'focus-visible:ring-white/35';
  const pillActive = onPaper ? 'bg-oxford/[0.08]' : 'bg-white/[0.08]';
  const pillHover = onPaper ? 'group-hover:bg-oxford/[0.05]' : 'group-hover:bg-white/[0.05]';
  const shortcutActive = onPaper ? 'text-oxford/75' : 'text-white/75';
  const shortcutIdle = onPaper
    ? 'text-oxford/30 group-hover:text-oxford/52'
    : 'text-white/30 group-hover:text-white/52';

  return (
    <button
      type="button"
      onClick={onClick}
      title={shortcut ? `${label} (${shortcut})` : label}
      className={`group type-meta w-full flex items-center justify-between gap-phi-3 px-1 cursor-pointer tracking-[0.06em] btn-interaction transition-colors focus-visible:outline-none focus-visible:ring-2 ${ring} ${
        active ? textActive : textIdle
      } ${compact ? 'min-h-[32px]' : 'min-h-[44px]'}`}
      style={{ transitionTimingFunction: 'var(--motion-ease)' }}
      aria-pressed={ariaPressed}
      aria-current={active ? 'page' : undefined}
    >
      <span
        className={`inline-block px-2 py-1 transition-[background-color,color] ${
          active ? pillActive : pillHover
        }`}
      >
        {label}
      </span>
      {shortcut ? (
        <span
          className={`tabular-nums transition-colors ${
            active ? shortcutActive : shortcutIdle
          }`}
          aria-hidden
        >
          {shortcut.padStart(2, '0')}
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
  navLink,
  pipelineState,
  pipelineIssueHelpOpen = false,
  onPipelineIssueHelpToggle,
  onPipelineOpenSettings,
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
        {/* Nav — workspace chrome only (wordmark + clock live in MainLayout above) */}
        {workspaceChrome ? (
          <div className="mt-phi-4 flex flex-col gap-0.5 w-full shrink-0">
              <SpineNavButton
                label="Deals"
                active={rightPanel !== 'system' && rightPanel !== 'feed'}
                ariaPressed={rightPanel !== 'system' && rightPanel !== 'feed'}
                onClick={() => onShowDeals!()}
                shortcut="1"
                compact
                surface="paper"
              />
              <SpineNavButton
                label="Signals"
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
          </div>
        ) : null}
        {workspaceChrome && pipelineState != null ? (
          <div className="mt-phi-4 flex w-full shrink-0 items-center justify-end px-1">
            <div className="relative inline-flex items-center gap-phi-2">
              {pipelineState === 'On' && (
                <span
                  className="h-1.5 w-1.5 shrink-0 rounded-none bg-oxford/50 pulse-soft"
                  aria-hidden
                />
              )}
              <span
                className={
                  pipelineState === 'Issue'
                    ? 'type-meta text-escalation'
                    : pipelineState === 'Off'
                      ? 'type-meta text-oxford/30'
                      : 'type-meta text-oxford/55'
                }
              >
                {pipelineState === 'On'
                  ? 'Pipeline active'
                  : pipelineState === 'Issue'
                    ? 'Pipeline issue'
                    : 'Pipeline off'}
              </span>
              {pipelineState === 'Issue' && onPipelineIssueHelpToggle && onPipelineOpenSettings ? (
                <>
                  <button
                    type="button"
                    onClick={onPipelineIssueHelpToggle}
                    className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-none border border-escalation/40 type-meta leading-none text-escalation hover:bg-escalation/10 btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-escalation/40"
                    aria-label="Pipeline issue details"
                    aria-expanded={pipelineIssueHelpOpen}
                  >
                    ?
                  </button>
                  {pipelineIssueHelpOpen ? (
                    <span className="absolute right-0 top-[calc(100%+8px)] z-20 w-56 border border-field-border bg-paper p-phi-3 text-left normal-case tracking-normal type-label-section leading-phi text-oxford">
                      Pipeline has a problem and may not process updates right now.
                      <button
                        type="button"
                        onClick={onPipelineOpenSettings}
                        className="mt-phi-2 block type-meta tracking-[0.06em] text-oxford/62 hover:text-oxford btn-interaction"
                      >
                        Open settings →
                      </button>
                    </span>
                  ) : null}
                </>
              ) : null}
            </div>
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
              onClick={requestLogout}
              disabled={agentActionPending}
              className="type-meta inline-flex min-h-[44px] items-center tracking-[0.06em] text-white/60 hover:text-white bg-transparent border-0 p-0 cursor-pointer btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35 disabled:opacity-60"
            >
              {agentActionPending ? 'Updating…' : 'Log out'}
            </button>
          </div>
        </div>
      </motion.header>

      <AgentLogoutModal {...logoutModalProps} />
    </>
  );
}
