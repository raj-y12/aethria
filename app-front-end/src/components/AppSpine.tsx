import { useEffect, useState } from 'react';
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

interface AppSpineProps {
  telemetry: SpineTelemetry;
  mandate: SpineMandate;
  /** True while a Dispatch lookup runs in the background. */
  dispatchActive: boolean;
  onDispatch: () => void;
}

export const SPINE_WORKSPACES: Array<{ href: string; label: string; shortcut: string }> = [
  { href: '/v1', label: 'Today', shortcut: '1' },
  { href: '/v1/flow', label: 'Flow', shortcut: '2' },
  { href: '/v1/portfolio', label: 'Portfolio', shortcut: '3' },
  { href: '/v1/fund', label: 'Fund', shortcut: '4' },
];

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

const PIPELINE_TONE: Record<SpinePipelineState, { text: string; dot: string }> = {
  Live: { text: 'text-white/72', dot: 'bg-white signal-dot-breathe' },
  Idle: { text: 'text-white/40', dot: 'bg-white/35' },
  Off: { text: 'text-white/28', dot: 'bg-white/18' },
  Stopping: { text: 'text-white/50', dot: 'bg-white/40 pulse-soft' },
  Issue: { text: 'text-escalation-bright', dot: 'bg-escalation-bright escalation-dot-active' },
};

/**
 * The spine — full-height oxford rail, present on every workspace. Carries the
 * product identity (wordmark), the three workspaces + Dispatch, the single
 * number that needs judgment, the active mandate, and the operator. Everything
 * else belongs to the workspace it serves.
 */
export default function AppSpine({ telemetry, mandate, dispatchActive, onDispatch }: AppSpineProps) {
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
  const heroLabel = hasEscalations ? 'Need ruling' : 'Open';
  const heroValue = hasEscalations ? telemetry.pendingEscalations : telemetry.openInProgressCount;
  const pipelineTone = PIPELINE_TONE[telemetry.pipelineState];

  return (
    <>
      <aside
        className="aethria-spine hidden lg:flex h-full min-h-0 flex-none flex-col justify-between bg-oxford px-phi-4 pb-phi-4 pt-phi-5"
        aria-label="Aethria"
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
            <p className="mt-phi-2 font-mono text-[10px] tabular-nums tracking-[0.08em] text-white/35" aria-hidden>
              {timeShort} · {dateShort}
            </p>
          </div>

          {/* ── Workspaces ───────────────────────────────────────── */}
          <nav className="flex flex-col gap-0.5" aria-label="Workspaces">
            {SPINE_WORKSPACES.map((item) => (
              <SpineNavButton
                key={item.href}
                label={item.label}
                active={isSpineRouteActive(item.href, pathname)}
                ariaPressed={isSpineRouteActive(item.href, pathname)}
                onClick={() => navigate(item.href)}
                shortcut={item.shortcut}
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
              surface="oxford"
              running={dispatchActive}
            />
          </nav>
        </div>

        <div className="flex min-h-0 flex-col gap-phi-4">
          {/* ── Judgment pressure ────────────────────────────────── */}
          <section aria-label="Pipeline overview" className="px-2">
            <div className="flex items-end justify-between gap-phi-3">
              <div className="min-w-0">
                <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-white/38">{heroLabel}</p>
                {hasEscalations ? (
                  <button
                    type="button"
                    onClick={() => navigate('/v1/flow?queue=escalated')}
                    title="Review escalations"
                    aria-label={`Review ${heroValue} items needing a ruling`}
                    className="mt-phi-1 block font-mono text-[clamp(1.6rem,2.4vw,2.25rem)] font-bold leading-none tracking-[-0.04em] tabular-nums text-escalation-bright transition-opacity hover:opacity-80 btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
                  >
                    {heroValue.toLocaleString()}
                  </button>
                ) : (
                  <p
                    className="mt-phi-1 font-mono text-[clamp(1.6rem,2.4vw,2.25rem)] font-bold leading-none tracking-[-0.04em] tabular-nums text-white/92"
                    aria-live="polite"
                  >
                    {heroValue.toLocaleString()}
                  </p>
                )}
              </div>
              <span
                className={`inline-flex shrink-0 items-center gap-phi-2 pb-px font-mono text-[10px] uppercase tracking-[0.10em] ${pipelineTone.text}`}
                title="Pipeline status"
              >
                <span className={`h-1.5 w-1.5 shrink-0 rounded-none ${pipelineTone.dot}`} aria-hidden />
                {telemetry.pipelineState}
              </span>
            </div>

            <p className="mt-phi-3 border-t border-white/[0.07] pt-phi-3 font-mono text-[10px] tracking-[0.04em] tabular-nums text-white/40">
              <span className="font-semibold text-white/75">{telemetry.totalCount.toLocaleString()}</span> total
              <span className="mx-phi-2 text-white/20" aria-hidden>·</span>
              <span className="font-semibold text-white/75">{telemetry.agentDecidedCount.toLocaleString()}</span> rec
              <span className="mx-phi-2 text-white/20" aria-hidden>·</span>
              <span className="font-semibold text-white/75">{telemetry.humanRuledCount.toLocaleString()}</span> ruled
            </p>

            {telemetry.pipelineState === 'Issue' ? (
              <Link
                to="/v1/settings"
                className="mt-phi-3 block font-mono text-[10px] uppercase tracking-[0.10em] text-escalation-bright/85 hover:text-escalation-bright btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
              >
                Pipeline needs attention →
              </Link>
            ) : null}

            {telemetry.newCount > 0 ? (
              <button
                type="button"
                onClick={() => navigate('/v1/flow?queue=new')}
                aria-label={`Triage ${telemetry.newCount} new ${telemetry.newCount === 1 ? 'company' : 'companies'}`}
                className="group mt-phi-3 flex w-full items-center gap-phi-2 border-t border-white/[0.07] pt-phi-3 text-left btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
              >
                <span className="h-1.5 w-1.5 shrink-0 rounded-none bg-white signal-dot-breathe" aria-hidden />
                <span className="font-mono text-[10px] tracking-[0.04em] tabular-nums text-white/50 transition-colors group-hover:text-white/85">
                  <span className="font-semibold text-white/80">{telemetry.newCount.toLocaleString()}</span> new · triage
                </span>
                <span className="ml-auto font-mono text-[10px] text-white/30 transition-colors group-hover:text-white/60" aria-hidden>→</span>
              </button>
            ) : null}
          </section>

          {/* ── Mandate ──────────────────────────────────────────── */}
          <button
            type="button"
            onClick={() => navigate(mandate.hasThesis ? '/v1/fund' : '/v1/settings')}
            title={mandate.summaryLine || undefined}
            aria-label={
              mandate.hasThesis
                ? `Active mandate: ${mandate.fundName || 'configured'} — open Fund`
                : 'No active thesis — open settings'
            }
            className="group flex w-full min-w-0 flex-col gap-phi-2 border-t border-white/[0.07] px-2 pt-phi-3 text-left btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
          >
            <span className="flex items-center justify-between gap-phi-2">
              <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-white/38">
                Mandate
                {mandate.hasThesis && mandate.versionNumber != null ? ` · v${mandate.versionNumber}` : ''}
              </span>
              <span
                className={`inline-flex shrink-0 items-center gap-phi-2 font-mono text-[10px] uppercase tracking-[0.10em] ${
                  mandate.hasThesis ? 'text-white/45' : 'text-escalation-bright/85'
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 shrink-0 rounded-none ${
                    mandate.hasThesis ? 'bg-white signal-dot-breathe' : 'bg-escalation-bright/80'
                  }`}
                  aria-hidden
                />
                {mandate.hasThesis ? 'Active' : 'Set up'}
              </span>
            </span>
            <span className="min-w-0 truncate font-sans text-[13px] font-semibold leading-[1.4] text-white/85 transition-colors group-hover:text-white">
              {mandate.hasThesis ? mandate.fundName || 'Active mandate' : 'No active thesis'}
            </span>
            <span className="min-w-0 truncate font-mono text-[10px] tracking-[0.06em] text-white/35 transition-colors group-hover:text-white/55">
              {mandate.hasThesis
                ? mandate.summaryLine || 'Open fund →'
                : 'Configure to start the pipeline →'}
            </span>
          </button>

          {/* ── Operator ─────────────────────────────────────────── */}
          <section aria-label="Operator" className="min-w-0 border-t border-white/[0.07] px-2 pt-phi-3">
            <p className="min-w-0 truncate font-sans text-[13px] font-semibold leading-[1.4] text-white/80" title={displayName}>
              {displayName}
            </p>
            <div className="mt-phi-2 flex items-center gap-phi-3">
              <Link
                to="/v1/settings"
                className="font-mono text-[10px] uppercase tracking-[0.10em] text-white/40 transition-colors hover:text-white/80 btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
              >
                Settings
              </Link>
              <span className="font-mono text-[9px] text-white/20" aria-hidden>·</span>
              <button
                type="button"
                onClick={requestLogout}
                disabled={agentActionPending}
                className="font-mono text-[10px] uppercase tracking-[0.10em] text-white/40 transition-colors hover:text-white/80 disabled:opacity-50 btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
              >
                {agentActionPending ? 'Updating...' : 'Log out'}
              </button>
            </div>
            {agentActionError ? (
              <p className="mt-phi-2 font-mono text-[10px] tracking-[0.06em] text-escalation-bright" role="status" aria-live="polite">
                {agentActionError}
              </p>
            ) : null}
          </section>
        </div>
      </aside>

      <AgentLogoutModal {...logoutModalProps} />
    </>
  );
}
