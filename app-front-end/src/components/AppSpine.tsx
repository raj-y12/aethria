import { useEffect, useState, type ReactNode } from 'react';
import { Link, useLocation, useNavigate } from 'react-router';
import { SpineNavButton } from './SystemBar';
import AgentLogoutModal from './AgentLogoutModal';
import { useAgentLogoutFlow } from '../hooks/useAgentLogoutFlow';

export type SpinePipelineState = 'Live' | 'Idle' | 'Off' | 'Issue' | 'Stopping';

export interface SpineTelemetry {
  /** Items awaiting a human ruling — the one number that matters. */
  pendingEscalations: number;
  /** Open / in-progress items (shown when nothing needs a ruling). */
  openInProgressCount: number;
  totalCount: number;
  agentDecidedCount: number;
  humanRuledCount: number;
  newCount: number;
  pipelineState: SpinePipelineState;
}

export interface SpineMandate {
  hasThesis: boolean;
  fundName: string;
  summaryLine: string;
  versionNumber: number | null;
}

/**
 * A room (e.g. Settings) can take over the spine's contextual regions: its
 * nav replaces the workspace nav, its footer replaces telemetry + mandate.
 * Identity (top) and operator (bottom) never change — one rail, always.
 */
export interface SpineOverride {
  nav: ReactNode;
  footer?: ReactNode;
}

interface AppSpineProps {
  telemetry: SpineTelemetry;
  mandate: SpineMandate;
  /** True while a Dispatch lookup runs in the background. */
  dispatchActive: boolean;
  onDispatch: () => void;
  override?: SpineOverride | null;
}

export const SPINE_WORKSPACES: Array<{ href: string; label: string; shortcut: string }> = [
  { href: '/v1', label: 'Home', shortcut: '1' },
  { href: '/v1/flow', label: 'Flow', shortcut: '2' },
  { href: '/v1/portfolio', label: 'Portfolio', shortcut: '3' },
  { href: '/v1/fund', label: 'Fund', shortcut: '4' },
];

export const SPINE_WIDTH = 'clamp(204px, 15vw, 248px)';

export function isSpineRouteActive(href: string, pathname: string): boolean {
  if (href === '/v1') {
    return pathname === '/v1' || pathname === '/v1/';
  }
  if (href === '/v1/flow') {
    return pathname.startsWith('/v1/flow') || pathname.startsWith('/v1/deal');
  }
  return pathname.startsWith(href);
}

function SpineRule() {
  return <div className="h-px w-full bg-white/[0.07]" aria-hidden />;
}

/** Instrument readout — mirrors room headers, scaled for the oxford rail. */
function SpineReadout({
  label,
  value,
  tone = 'default',
  onClick,
}: {
  label: string;
  value: string;
  tone?: 'default' | 'escalation';
  onClick?: () => void;
}) {
  const valueTone = tone === 'escalation' ? 'text-escalation-bright' : 'text-white/[0.92]';
  const body = (
    <>
      <span
        className={`type-data text-[clamp(17px,1.35vw,21px)] leading-none ${valueTone}`}
      >
        {value}
      </span>
      <span className="type-label-section type-label-inverse mt-phi-1 leading-none">{label}</span>
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className="flex min-w-0 flex-col items-start text-left transition-opacity hover:opacity-80 btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
      >
        {body}
      </button>
    );
  }

  return <div className="flex min-w-0 flex-col items-start">{body}</div>;
}

const PIPELINE_TONE: Record<SpinePipelineState, { text: string; dot: string }> = {
  Live: { text: 'text-white/[0.72]', dot: 'bg-white signal-dot-breathe' },
  Idle: { text: 'text-white/60', dot: 'bg-white/35' },
  Off: { text: 'text-white/60', dot: 'bg-white/[0.18]' },
  Stopping: { text: 'text-white/60', dot: 'bg-white/40 pulse-soft' },
  Issue: { text: 'text-escalation-bright', dot: 'bg-escalation-bright escalation-dot-active' },
};

/**
 * The spine — full-height oxford rail, present on every workspace. Carries the
 * product identity (wordmark), the three workspaces + Dispatch, the single
 * number that needs judgment, the active mandate, and the operator. Everything
 * else belongs to the workspace it serves.
 */
export default function AppSpine({ telemetry, mandate, dispatchActive, onDispatch, override }: AppSpineProps) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const {
    displayName,
    agentActionPending,
    agentActionError,
    requestLogout,
    logoutModalProps,
  } = useAgentLogoutFlow();

  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const tick = () => setTime(new Date());
    tick();
    const t = setInterval(tick, 60_000);
    return () => clearInterval(t);
  }, []);
  const timeShort = time.toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit' });
  const dateShort = time.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }).toUpperCase();

  const hasEscalations = telemetry.pendingEscalations > 0;
  const pipelineTone = PIPELINE_TONE[telemetry.pipelineState];

  return (
    <>
      <aside
        className="aethria-spine hidden lg:flex h-full min-h-0 flex-none flex-col justify-between bg-oxford px-phi-4 pb-phi-4 pt-phi-5"
        aria-label="Aethria"
        style={{ width: SPINE_WIDTH }}
      >
        <div className="flex min-h-0 flex-col gap-phi-4">
          {/* ── Identity ─────────────────────────────────────────── */}
          <div className="px-2">
            <Link
              to="/v1"
              className="font-wordmark text-[clamp(19px,1.5vw,24px)] font-medium leading-tight text-paper btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
            >
              Aethria<span className="wordmark-dot wordmark-dot--inverse">.</span>
            </Link>
            <p className="type-meta type-meta-inverse mt-phi-2 tabular-nums" aria-hidden>
              {timeShort} · {dateShort}
            </p>
          </div>

          {override ? (
            /* ── Room nav (e.g. Settings sections) ──────────────── */
            <nav className="flex min-h-0 flex-col gap-0.5 overflow-y-auto" aria-label="Section navigation">
              {override.nav}
            </nav>
          ) : (
            /* ── Workspaces ─────────────────────────────────────── */
            <nav className="flex flex-col gap-0.5" aria-label="Workspaces">
              {SPINE_WORKSPACES.map((item) => (
                <SpineNavButton
                  key={item.href}
                  label={item.label}
                  active={isSpineRouteActive(item.href, pathname)}
                  ariaPressed={isSpineRouteActive(item.href, pathname)}
                  onClick={() => navigate(item.href)}
                  shortcut={item.shortcut}
                  compact
                  surface="oxford"
                />
              ))}
              <div className="my-phi-2 px-2">
                <SpineRule />
              </div>
              <SpineNavButton
                label="Dispatch"
                active={false}
                ariaPressed={false}
                onClick={onDispatch}
                shortcut="⌘K"
                compact
                surface="oxford"
                running={dispatchActive}
              />
            </nav>
          )}
        </div>

        <div className="flex min-h-0 flex-col gap-phi-4">
          {override ? (
            override.footer ?? null
          ) : (
            <>
              {/* ── Pipeline readouts + mandate — a ruled section, not a slab ── */}
              <section
                aria-label="Pipeline and mandate"
                className="border-t border-white/10 px-2 pt-phi-4"
              >
                <div className="flex items-baseline justify-between gap-phi-2">
                  <span className="type-label-section type-label-inverse">Pipeline</span>
                  <span
                    className={`type-status inline-flex shrink-0 items-center gap-phi-2 ${pipelineTone.text}`}
                  >
                    <span className={`h-1.5 w-1.5 shrink-0 rounded-none ${pipelineTone.dot}`} aria-hidden />
                    {telemetry.pipelineState}
                  </span>
                </div>

                {telemetry.pipelineState === 'Issue' ? (
                  <Link
                    to="/v1/settings"
                    className="type-action mt-phi-2 block text-escalation-bright/85 transition-colors hover:text-escalation-bright btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
                  >
                    Needs attention →
                  </Link>
                ) : null}

                {/* One number that needs judgment — Need ruling when there is
                    work to rule, otherwise Open. The room headers carry the full
                    readout set; the spine stays a single ambient signal. */}
                <div className="mt-phi-4" aria-live="polite">
                  <SpineReadout
                    label={hasEscalations ? 'Need ruling' : 'Open'}
                    value={(hasEscalations ? telemetry.pendingEscalations : telemetry.openInProgressCount).toLocaleString()}
                    tone={hasEscalations ? 'escalation' : 'default'}
                    onClick={
                      hasEscalations ? () => navigate('/v1/flow?queue=escalated') : () => navigate('/v1/flow')
                    }
                  />
                  <p className="type-meta type-meta-inverse mt-phi-2 tabular-nums">
                    {hasEscalations
                      ? `${telemetry.openInProgressCount.toLocaleString()} open`
                      : `${telemetry.totalCount.toLocaleString()} in pipeline`}
                    {telemetry.newCount > 0 ? ` · ${telemetry.newCount.toLocaleString()} new` : ''}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => navigate(mandate.hasThesis ? '/v1/fund' : '/v1/settings')}
                  title={mandate.summaryLine || undefined}
                  aria-label={
                    mandate.hasThesis
                      ? `Active mandate: ${mandate.fundName || 'configured'} — open Fund`
                      : 'No active thesis — open settings'
                  }
                  className="group mt-phi-4 block w-full min-w-0 border-t border-white/10 pt-phi-3 text-left btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
                >
                  <span className="type-label-section type-label-inverse">
                    Mandate
                    {mandate.hasThesis && mandate.versionNumber != null ? ` · v${mandate.versionNumber}` : ''}
                    {!mandate.hasThesis ? ' · set up' : ''}
                  </span>
                  <span className="mt-phi-1 block min-w-0 truncate font-sans text-[12px] font-medium leading-snug text-white/85 transition-colors group-hover:text-white">
                    {mandate.hasThesis ? mandate.fundName || 'Active mandate' : 'No active thesis'}
                  </span>
                  {mandate.hasThesis && mandate.summaryLine ? (
                    <span className="type-meta type-meta-inverse mt-0.5 block min-w-0 truncate transition-colors group-hover:text-white">
                      {mandate.summaryLine}
                    </span>
                  ) : null}
                </button>
              </section>
            </>
          )}

          {/* ── Operator — Today footer voice ── */}
          <footer aria-label="Operator" className="min-w-0 border-t border-white/10 px-2 pt-phi-3">
            <p className="type-label-section type-label-inverse truncate" title={displayName}>
              {displayName}
            </p>
            <div className="mt-phi-2 flex items-center gap-phi-4">
              <Link
                to="/v1/settings"
                className="type-action type-action-inverse transition-colors hover:text-white btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
              >
                Settings
              </Link>
              <button
                type="button"
                onClick={requestLogout}
                disabled={agentActionPending}
                className="type-action type-action-inverse transition-colors hover:text-white disabled:opacity-50 btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
              >
                {agentActionPending ? 'Updating…' : 'Log out'}
              </button>
            </div>
            {agentActionError ? (
              <p className="type-meta mt-phi-2 text-escalation-bright" role="status" aria-live="polite">
                {agentActionError}
              </p>
            ) : null}
          </footer>
        </div>
      </aside>

      <AgentLogoutModal {...logoutModalProps} />
    </>
  );
}
