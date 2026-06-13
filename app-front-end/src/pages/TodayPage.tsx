import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { motion } from 'framer-motion';
import Reveal from '../components/Reveal';
import { useAppFrame } from '../components/AppFrame';
import AgentLogoutModal from '../components/AgentLogoutModal';
import { useAgentLogoutFlow } from '../hooks/useAgentLogoutFlow';
import { useSinceAwaySummary } from '../hooks/useActivitySummary';
import { usePrefersReducedMotion } from '../hooks';
import { transitionOrReduced } from '../design-system/motion';
import { tokens } from '../design-system/tokens';
import { isDealUnresolved } from '../lib/dealState';
import type { SystemData } from '../hooks/useSystemData';
import type { Startup } from '../types/startup';

function recOf(s: Startup): string | null {
  const r = s.partner?.recommendation;
  return typeof r === 'string' && r ? r.toUpperCase() : null;
}

/** A control key — numeral, label, and live reading stacked; four keys stay inline. */
function HomeKey({
  numeral,
  label,
  detail,
  detailTone = 'default',
  onClick,
}: {
  numeral: string;
  label: string;
  detail: string;
  detailTone?: 'default' | 'escalation';
  onClick: () => void;
}) {
  const reduceMotion = usePrefersReducedMotion();
  const hoverEase = tokens.motion.ease;
  const hoverDuration = tokens.motion.duration.short;
  const labelTransition = transitionOrReduced(reduceMotion, {
    duration: hoverDuration,
    ease: hoverEase,
  });

  return (
    <motion.button
      type="button"
      onClick={onClick}
      initial={false}
      whileHover={{ backgroundColor: 'var(--color-oxford)' }}
      whileTap={reduceMotion ? undefined : { scale: 0.985 }}
      transition={labelTransition}
      className="group flex min-w-0 flex-1 flex-col items-center justify-center gap-phi-2 border-0 bg-paperDeep px-phi-4 py-phi-5 text-oxford focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40"
    >
      <span
        className="font-mono text-[9px] tracking-[0.14em] text-oxford/35 transition-colors duration-[220ms] ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:text-paper/50"
        aria-hidden
      >
        {numeral}
      </span>
      <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-oxford/85 transition-colors duration-[220ms] ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:text-paper">
        {label}
      </span>
      <span
        className={`text-center font-mono text-[9px] leading-snug tracking-[0.04em] tabular-nums transition-colors duration-[220ms] ease-[cubic-bezier(0.16,1,0.3,1)] ${
          detailTone === 'escalation'
            ? 'text-escalation/85 group-hover:text-escalation-bright'
            : 'text-oxford/40 group-hover:text-paper/55'
        }`}
      >
        {detail}
      </span>
    </motion.button>
  );
}

/**
 * Today — the front door. Modelled on the Dispatch takeover (the house voice):
 * no sidebar, one centered column, the system speaking in serif, and the four
 * doors as control keys in the middle of the canvas.
 */
export default function TodayPage({ data }: { data: SystemData }) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { openDispatch, dispatchActive } = useAppFrame();
  // Acknowledges the away report (marks it seen) — the login screen is the one
  // place that presents it. Rendering it here repeated the headline and shoved
  // the layout down when the numbers arrived mid-entrance.
  useSinceAwaySummary();
  const {
    displayName,
    agentActionPending,
    requestLogout,
    logoutModalProps,
  } = useAgentLogoutFlow();
  const { startups } = data;

  // Legacy deep links (/v1?open=…, /v1?queue=…) belong to Flow.
  useEffect(() => {
    if (searchParams.get('open') || searchParams.get('queue')) {
      navigate(`/v1/flow?${searchParams.toString()}`, { replace: true });
    }
  }, [searchParams, navigate]);

  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(t);
  }, []);

  // ── The situation ──────────────────────────────────────────────────────────
  const needRuling = data.pendingEscalationCount ?? 0;
  const newCount = useMemo(() => startups.filter((s) => s.is_new_to_user).length, [startups]);
  const openCount = useMemo(() => startups.filter(isDealUnresolved).length, [startups]);
  const convictionCount = useMemo(() => startups.filter((s) => recOf(s) === 'INVEST').length, [startups]);
  const watchTotal = data.watchlistAnalytics.total;
  const mandateVersion = data.fundThesisRuntime?.active_version_number ?? null;
  const fundName = data.settings?.fund_identity?.fund_name?.trim() || '';

  const headline =
    needRuling > 0
      ? `${needRuling} ${needRuling === 1 ? 'matter awaits' : 'matters await'} your ruling.`
      : newCount > 0
        ? `${newCount} new ${newCount === 1 ? 'company' : 'companies'} since you left.`
        : openCount > 0
          ? 'The pipeline is working. Nothing needs you.'
          : 'The desk is clear.';

  const subline = [
    `${startups.length.toLocaleString()} in pipeline`,
    `${openCount.toLocaleString()} open`,
    convictionCount > 0 ? `${convictionCount.toLocaleString()} conviction` : null,
  ]
    .filter(Boolean)
    .join(' · ');

  const eyebrow = `${now
    .toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })
    .toUpperCase()} · ${now.toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit' })}`;

  return (
    <div className="paper-dot-grid relative flex h-full min-h-0 flex-col overflow-y-auto overscroll-contain">
      <div className="flex min-h-full w-full flex-1 flex-col items-center justify-center px-phi-6 py-phi-7">
        {/* ── The mark ── */}
        <Reveal delay={0.02} y={-6}>
          <p className="text-center font-wordmark text-[clamp(22px,2vw,28px)] font-medium leading-tight text-oxford">
            Aethria<span className="wordmark-dot">.</span>
          </p>
        </Reveal>

        {/* ── The situation, spoken ── */}
        <Reveal delay={0.1} className="mt-phi-7">
          <p className="text-center font-mono text-[11px] uppercase tracking-[0.16em] tabular-nums text-oxford/40">
            {eyebrow}
          </p>
        </Reveal>

        <Reveal delay={0.16} y={12} className="mt-phi-4">
          <h1 className="type-display m-0 max-w-[24ch] text-center text-[clamp(30px,4.2vw,54px)] font-medium leading-[1.1] text-oxford">
            {headline}
          </h1>
        </Reveal>

        <Reveal delay={0.24} className="mt-phi-4">
          <p className="text-center font-mono text-[11px] tracking-[0.06em] tabular-nums text-oxford/45">
            {subline}
          </p>
        </Reveal>

        {/* ── The doors ── */}
        <Reveal delay={0.32} className="mt-phi-7 w-full max-w-[48rem]">
          <div className="flex w-full flex-nowrap items-stretch justify-center gap-phi-3" role="navigation" aria-label="Workspaces">
            <HomeKey
              numeral="II"
              label="Flow"
              detail={
                needRuling > 0
                  ? `${needRuling} need ruling`
                  : newCount > 0
                    ? `${newCount} new`
                    : `${openCount} open`
              }
              detailTone={needRuling > 0 ? 'escalation' : 'default'}
              onClick={() => navigate('/v1/flow')}
            />
            <HomeKey
              numeral="III"
              label="Portfolio"
              detail={`${convictionCount} conviction · ${watchTotal} watch`}
              onClick={() => navigate('/v1/portfolio')}
            />
            <HomeKey
              numeral="IV"
              label="Fund"
              detail={mandateVersion != null ? `Mandate v${mandateVersion}` : 'No mandate'}
              onClick={() => navigate('/v1/fund')}
            />
            <HomeKey
              numeral="⌘K"
              label="Dispatch"
              detail={dispatchActive ? 'Lookup running' : 'Look up a company'}
              onClick={openDispatch}
            />
          </div>
        </Reveal>

        {/* ── The footer bar — Dispatch's micro-action language ── */}
        <Reveal delay={0.42} className="mt-phi-8">
          <div className="flex flex-wrap items-center justify-center gap-x-1 gap-y-1">
            <span className="type-meta border-b border-oxford/10 px-1 pb-0.5 uppercase tracking-[0.12em] text-oxford/40">
              {displayName}
            </span>
            {fundName || mandateVersion != null ? (
              <>
                <span className="type-meta px-1 text-oxford/20" aria-hidden>·</span>
                <Link
                  to="/v1/fund"
                  className="type-meta border-b border-oxford/10 px-1 pb-0.5 uppercase tracking-[0.12em] text-oxford/30 transition-colors hover:text-oxford/50 btn-interaction"
                >
                  {fundName || `Mandate v${mandateVersion}`}
                </Link>
              </>
            ) : null}
            <span className="type-meta px-1 text-oxford/20" aria-hidden>·</span>
            <Link
              to="/v1/settings"
              className="type-meta border-b border-oxford/10 px-1 pb-0.5 uppercase tracking-[0.12em] text-oxford/30 transition-colors hover:text-oxford/50 btn-interaction"
            >
              Settings
            </Link>
            <span className="type-meta px-1 text-oxford/20" aria-hidden>·</span>
            <button
              type="button"
              onClick={requestLogout}
              disabled={agentActionPending}
              className="type-meta border-b border-oxford/10 px-1 pb-0.5 uppercase tracking-[0.12em] text-oxford/30 transition-colors hover:text-oxford/50 disabled:opacity-50 btn-interaction"
            >
              {agentActionPending ? 'Updating…' : 'Log out'}
            </button>
          </div>
        </Reveal>
      </div>

      <AgentLogoutModal {...logoutModalProps} />
    </div>
  );
}
