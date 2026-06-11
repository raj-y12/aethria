import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { motion } from 'framer-motion';
import { useAppFrame } from '../components/AppFrame';
import AgentLogoutModal from '../components/AgentLogoutModal';
import { useAgentLogoutFlow } from '../hooks/useAgentLogoutFlow';
import { useSinceAwaySummary } from '../hooks/useActivitySummary';
import { isDealUnresolved } from '../lib/dealState';
import type { SystemData } from '../hooks/useSystemData';
import type { Startup } from '../types/startup';

const EASE = [0.16, 1, 0.3, 1] as const;

/** Dispatch-style staggered reveal — the takeover's motion language is the house voice. */
function Reveal({
  delay,
  y = 10,
  className,
  children,
}: {
  delay: number;
  y?: number;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: EASE, delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

function recOf(s: Startup): string | null {
  const r = s.partner?.recommendation;
  return typeof r === 'string' && r ? r.toUpperCase() : null;
}

/**
 * A control key — one of the four doors. Flow is the single solid oxford key
 * (the product's one action is making judgments); the rest are quiet ghosts.
 */
function HomeKey({
  numeral,
  label,
  detail,
  detailTone = 'default',
  solid = false,
  onClick,
}: {
  numeral: string;
  label: string;
  detail: string;
  detailTone?: 'default' | 'escalation';
  solid?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`group flex min-h-[112px] flex-col items-center justify-center gap-phi-2 rounded-none border px-phi-4 py-phi-5 transition-colors btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 ${
        solid
          ? 'border-oxford bg-oxford text-paper hover:bg-oxford/[0.92]'
          : 'border-oxford/[0.14] bg-transparent text-oxford hover:border-oxford/45 hover:bg-oxford/[0.03]'
      }`}
    >
      <span
        className={`font-mono text-[10px] tracking-[0.14em] ${solid ? 'text-paper/45' : 'text-oxford/30'}`}
        aria-hidden
      >
        {numeral}
      </span>
      <span
        className={`font-mono text-[12px] font-semibold uppercase tracking-[0.16em] ${
          solid ? 'text-paper' : 'text-oxford/85'
        }`}
      >
        {label}
      </span>
      <span
        className={`font-mono text-[10px] tracking-[0.06em] tabular-nums ${
          solid
            ? detailTone === 'escalation'
              ? 'text-escalation-bright'
              : 'text-paper/55'
            : detailTone === 'escalation'
              ? 'text-escalation/85'
              : 'text-oxford/40'
        }`}
      >
        {detail}
      </span>
    </button>
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
  const sinceAway = useSinceAwaySummary();
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
          <h1 className="type-display m-0 max-w-[18ch] text-center text-[clamp(30px,4.2vw,54px)] font-medium leading-[1.1] text-oxford">
            {headline}
          </h1>
        </Reveal>

        <Reveal delay={0.24} className="mt-phi-4">
          <p className="text-center font-mono text-[11px] tracking-[0.06em] tabular-nums text-oxford/45">
            {subline}
          </p>
          {sinceAway ? (
            <p className="mt-phi-2 text-center font-mono text-[10px] tracking-[0.06em] tabular-nums text-oxford/35">
              While you were away — {sinceAway.found} discovered · {sinceAway.reviewed} evaluated ·{' '}
              {sinceAway.agent_decided ?? sinceAway.decided} decided
              {sinceAway.escalations > 0 ? (
                <span className="text-escalation/80"> · {sinceAway.escalations} escalated</span>
              ) : null}
            </p>
          ) : null}
        </Reveal>

        {/* ── The doors ── */}
        <Reveal delay={0.32} className="mt-phi-7 w-full max-w-[42rem]">
          <div className="grid grid-cols-2 gap-phi-3 sm:grid-cols-4" role="navigation" aria-label="Workspaces">
            <HomeKey
              numeral="II"
              label="Flow"
              solid
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
          <div className="flex flex-wrap items-center justify-center gap-x-1 gap-y-1 border-b border-oxford/10 pb-0.5">
            <span className="type-meta px-1 uppercase tracking-[0.12em] text-oxford/40">{displayName}</span>
            {fundName || mandateVersion != null ? (
              <>
                <span className="type-meta px-1 text-oxford/20" aria-hidden>·</span>
                <Link
                  to="/v1/fund"
                  className="type-meta px-1 uppercase tracking-[0.12em] text-oxford/30 transition-colors hover:text-oxford/50 btn-interaction"
                >
                  {fundName || `Mandate v${mandateVersion}`}
                </Link>
              </>
            ) : null}
            <span className="type-meta px-1 text-oxford/20" aria-hidden>·</span>
            <Link
              to="/v1/settings"
              className="type-meta px-1 uppercase tracking-[0.12em] text-oxford/30 transition-colors hover:text-oxford/50 btn-interaction"
            >
              Settings
            </Link>
            <span className="type-meta px-1 text-oxford/20" aria-hidden>·</span>
            <button
              type="button"
              onClick={requestLogout}
              disabled={agentActionPending}
              className="type-meta px-1 uppercase tracking-[0.12em] text-oxford/30 transition-colors hover:text-oxford/50 disabled:opacity-50 btn-interaction"
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
