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

/**
 * Door hover: the cell dissolves to oxford and type inverts to paper — a calm
 * crossfade, significant but restrained.
 */
const EASE = 'ease-[cubic-bezier(0.16,1,0.3,1)]';

/**
 * A door — one entry in the editorial nav band. Numeral, label, and a quiet
 * reading. On hover: the cell dissolves to oxford and the type inverts to paper.
 */
function HomeDoor({
  numeral,
  label,
  detail,
  tone = 'default',
  index,
  onClick,
}: {
  numeral: string;
  label: string;
  detail: string;
  tone?: 'default' | 'escalation';
  index: number;
  onClick: () => void;
}) {
  const reduceMotion = usePrefersReducedMotion();

  return (
    <motion.button
      type="button"
      onClick={onClick}
      aria-label={`${label}. ${detail}.`}
      initial={reduceMotion ? false : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={transitionOrReduced(reduceMotion, {
        duration: tokens.motion.duration.micro,
        ease: tokens.motion.ease,
        delay: 0.18 + index * 0.04,
      })}
      className="group relative flex flex-col items-center gap-phi-3 overflow-hidden px-phi-5 py-phi-6 text-oxford focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-oxford/30"
    >
      {/* The cell dissolves to a solid oxford plate — a crossfade, no motion. */}
      <span
        aria-hidden
        className={`pointer-events-none absolute inset-0 z-0 bg-oxford opacity-0 transition-opacity duration-[360ms] ${EASE} group-hover:opacity-100`}
      />

      <span
        className={`relative z-10 font-mono text-[10px] tracking-[0.2em] transition-[transform,color] duration-300 ${EASE} group-hover:-translate-y-[3px] text-oxford/35 group-hover:text-paper/55 group-hover:delay-100`}
        aria-hidden
      >
        {numeral}
      </span>
      <span className="relative z-10 inline-block px-[3px]">
        <span
          className={`block font-mono text-[12px] font-semibold uppercase tracking-[0.18em] transition-[color] duration-300 ${EASE} text-oxford/80 group-hover:text-paper group-hover:delay-100`}
        >
          {label}
        </span>
      </span>
      <span
        className={`relative z-10 text-center font-mono text-[9.5px] leading-snug tracking-[0.06em] tabular-nums transition-colors duration-300 ${EASE} ${
          tone === 'escalation'
            ? 'text-escalation/90 group-hover:text-escalation-bright'
            : 'text-oxford/45 group-hover:text-paper/60 group-hover:delay-100'
        }`}
      >
        {detail}
      </span>
    </motion.button>
  );
}

/**
 * Home — the front door. One centered column on paper: the mark, the situation
 * spoken in serif, and a single editorial band of four doors into the
 * workspaces. Sleek and quiet; the type and the hairlines do the work.
 */
export default function HomePage({ data }: { data: SystemData }) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { openDispatch, dispatchActive } = useAppFrame();
  // Marks the away report seen — the login screen is where it is presented.
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
    .join('  ·  ');

  const eyebrow = `${now
    .toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })
    .toUpperCase()} · ${now.toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit' })}`;

  return (
    <div className="paper-dot-grid relative flex h-full min-h-0 flex-col overflow-y-auto overscroll-contain">
      <div className="flex min-h-full w-full flex-1 flex-col items-center justify-center px-phi-6 py-phi-7">
        {/* ── The mark ── */}
        <Reveal delay={0.02} y={-6}>
          <p className="text-center font-wordmark text-[clamp(19px,1.5vw,24px)] font-medium leading-tight text-oxford">
            Aethria<span className="wordmark-dot">.</span>
          </p>
        </Reveal>

        {/* ── The situation, spoken ── */}
        <Reveal delay={0.1} className="mt-phi-7">
          <p className="text-center font-mono text-[10px] uppercase tracking-[0.22em] tabular-nums text-oxford/40">
            {eyebrow}
          </p>
        </Reveal>

        <Reveal delay={0.16} y={10} className="mt-phi-5">
          <h1 className="type-display m-0 max-w-[22ch] text-center text-[clamp(32px,4.6vw,58px)] font-medium leading-[1.06] tracking-[-0.015em] text-oxford">
            {headline}
          </h1>
        </Reveal>

        <Reveal delay={0.24} className="mt-phi-5">
          <p className="text-center font-mono text-[10.5px] tracking-[0.1em] tabular-nums text-oxford/45">
            {subline}
          </p>
        </Reveal>

        {/* ── The doors — one editorial band ── */}
        <div className="mt-phi-8 w-full max-w-[46rem] border-y border-oxford/[0.12]">
          <div
            className="grid grid-cols-4 divide-x divide-oxford/[0.08]"
            role="navigation"
            aria-label="Workspaces"
          >
            <HomeDoor
              numeral="II"
              label="Flow"
              detail={needRuling > 0 ? `${needRuling} need ruling` : `${openCount} open`}
              tone={needRuling > 0 ? 'escalation' : 'default'}
              index={0}
              onClick={() => navigate('/v1/flow')}
            />
            <HomeDoor
              numeral="III"
              label="Portfolio"
              detail={`${convictionCount} conviction · ${watchTotal} watch`}
              index={1}
              onClick={() => navigate('/v1/portfolio')}
            />
            <HomeDoor
              numeral="IV"
              label="Fund"
              detail={mandateVersion != null ? `Mandate v${mandateVersion}` : 'No mandate'}
              index={2}
              onClick={() => navigate('/v1/fund')}
            />
            <HomeDoor
              numeral="⌘K"
              label="Dispatch"
              detail={dispatchActive ? 'Lookup running' : 'Look up a company'}
              index={3}
              onClick={openDispatch}
            />
          </div>
        </div>

        {/* ── The footer bar — Dispatch's micro-action language ── */}
        <Reveal delay={0.36} className="mt-phi-8">
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
