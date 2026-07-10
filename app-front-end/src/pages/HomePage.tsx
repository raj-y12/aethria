import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { motion } from 'framer-motion';
import Reveal from '../components/Reveal';
import { useAppFrame } from '../components/AppFrame';
import AgentLogoutModal from '../components/AgentLogoutModal';
import { useAgentLogoutFlow } from '../hooks/useAgentLogoutFlow';
import { useSinceAwaySummary } from '../hooks/useActivitySummary';
import { usePrefersReducedMotion } from '../hooks';
import { useFundReadiness } from '../hooks/useFundReadiness';
import { transitionOrReduced } from '../design-system/motion';
import { tokens } from '../design-system/tokens';
import { getDealAttentionReason, getDeskAttention, isDealUnresolved } from '../lib/dealState';
import type { SystemData } from '../hooks/useSystemData';
import type { Startup } from '../types/startup';

function recOf(s: Startup): string | null {
  const r = s.partner?.recommendation;
  return typeof r === 'string' && r ? r.toUpperCase() : null;
}

/**
 * Door hover: a whisper of oxford tint lifts the cell, a hairline draws in from
 * the centre, and the type rises and deepens — sleek, clean, chic. No slab.
 */
const EASE = 'ease-[cubic-bezier(0.16,1,0.3,1)]';

/** A door — one entry in the editorial nav band. Numeral, label, and a quiet reading. */
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
      {/* A whisper of oxford tint lifts the cell — airy, never a slab. */}
      <span
        aria-hidden
        className={`pointer-events-none absolute inset-0 z-0 bg-oxford opacity-0 transition-opacity duration-[420ms] ${EASE} group-hover:opacity-[0.04]`}
      />
      {/* An editorial hairline that draws in from the centre. */}
      <span
        aria-hidden
        className={`pointer-events-none absolute inset-x-phi-5 bottom-[14px] z-10 h-px origin-center scale-x-0 transition-transform duration-[420ms] ${EASE} group-hover:scale-x-100 ${
          tone === 'escalation' ? 'bg-escalation/70' : 'bg-oxford/45'
        }`}
      />

      <span
        className={`type-data relative z-10 transition-[transform,color] duration-300 ${EASE} group-hover:-translate-y-[2px] text-oxford/60 group-hover:text-oxford/70`}
        aria-hidden
      >
        {numeral}
      </span>
      <span className="relative z-10 inline-block px-[3px]">
        <span
          className={`type-action type-action-strong block transition-[transform,color] duration-300 ${EASE} group-hover:-translate-y-[1px] group-hover:text-oxford`}
        >
          {label}
        </span>
      </span>
      <span
        className={`type-meta relative z-10 text-center leading-snug tabular-nums transition-colors duration-300 ${EASE} ${
          tone === 'escalation'
            ? 'text-escalation/90 group-hover:text-escalation-bright'
            : 'text-oxford/60 group-hover:text-oxford/70'
        }`}
      >
        {detail}
      </span>
    </motion.button>
  );
}

/**
 * Home — the front door as a briefing. One centered column on paper: the mark,
 * the situation spoken in serif with a since-you-left digest, the few deals on
 * the desk (the door to Flow), and two quiet doors to Portfolio and Fund.
 * Content doubles as navigation; the type and the hairlines do the work.
 */
export default function HomePage({ data }: { data: SystemData }) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { openDispatch, dispatchActive } = useAppFrame();
  // What the agents did since the last visit (marks the report seen; null when
  // the login screen already presented it or nothing happened).
  const sinceAway = useSinceAwaySummary();
  const {
    displayName,
    agentActionPending,
    requestLogout,
    logoutModalProps,
  } = useAgentLogoutFlow();
  const { mandatePublished, loading: fundReadinessLoading } = useFundReadiness();
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

  // ── The briefing ───────────────────────────────────────────────────────────
  const attention = useMemo(() => getDeskAttention(startups), [startups]);
  const attentionOverflow = Math.max(0, openCount - attention.length);

  const digest = useMemo(() => {
    if (!sinceAway) return null;
    const parts = [
      sinceAway.found > 0 ? `${sinceAway.found} scouted` : null,
      sinceAway.reviewed > 0 ? `${sinceAway.reviewed} reviewed` : null,
      (sinceAway.agent_decided ?? sinceAway.decided) > 0
        ? `${sinceAway.agent_decided ?? sinceAway.decided} decided`
        : null,
      sinceAway.escalations > 0 ? `${sinceAway.escalations} escalated` : null,
    ].filter(Boolean);
    return parts.length > 0 ? `Since you left · ${parts.join(' · ')}` : null;
  }, [sinceAway]);

  const mandateAmended = data.fundThesisRuntime?.fund_thesis_updated_at
    ? new Date(data.fundThesisRuntime.fund_thesis_updated_at).toLocaleDateString('en-GB', {
        day: 'numeric',
        month: 'short',
      })
    : null;

  const eyebrow = `${now
    .toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })
    .toUpperCase()} · ${now.toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit' })}`;

  // First-run: no mandate published yet. Show a quiet editorial prompt.
  // We wait until the readiness check resolves (loading=false) to avoid a
  // flash for returning users — the hook defaults mandatePublished:true on
  // error so users are never falsely trapped.
  const showFirstRun = !fundReadinessLoading && !mandatePublished;

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
          <p className="type-label-section text-center tabular-nums">
            {eyebrow}
          </p>
        </Reveal>

        {showFirstRun ? (
          <>
            <Reveal delay={0.16} y={10} className="mt-phi-5">
              <h1 className="type-display m-0 max-w-[22ch] text-center text-[clamp(32px,4.6vw,58px)] font-medium leading-[1.06] tracking-[-0.015em] text-oxford">
                Define your mandate.
              </h1>
            </Reveal>

            <Reveal delay={0.24} className="mt-phi-5">
              <p className="type-note text-center text-oxford/60">
                Aethria won't scout or evaluate until a fund mandate is published.
              </p>
            </Reveal>

            <Reveal delay={0.32} className="mt-phi-7">
              <Link
                to="/v1/settings"
                className="type-action border-b border-oxford/30 px-1 pb-0.5 transition-colors hover:text-oxford btn-interaction"
              >
                Set mandate →
              </Link>
            </Reveal>
          </>
        ) : (
          <>
            <Reveal delay={0.16} y={10} className="mt-phi-5">
              <h1 className="type-display m-0 max-w-[22ch] text-center text-[clamp(32px,4.6vw,58px)] font-medium leading-[1.06] tracking-[-0.015em] text-oxford">
                {headline}
              </h1>
            </Reveal>

            <Reveal delay={0.24} className="mt-phi-5">
              <p className="type-meta text-center tabular-nums">
                {subline}
              </p>
            </Reveal>

            {digest && (
              <Reveal delay={0.3} className="mt-phi-3">
                <p className="type-meta text-center tabular-nums">
                  {digest}
                </p>
              </Reveal>
            )}

            {/* ── On the desk — the door to Flow, carrying its scent ── */}
            {attention.length > 0 && (
              <Reveal delay={0.34} className="mt-phi-7 w-full max-w-[46rem]">
                <button
                  type="button"
                  onClick={() => navigate('/v1/flow')}
                  aria-label={`On the desk: ${attention.map((s) => s.scout.name).join(', ')}. Open Flow.`}
                  className={`group relative block w-full overflow-hidden border-y border-oxford/[0.12] px-phi-5 py-phi-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-oxford/30`}
                >
                  {/* The same whisper of oxford tint as the doors. */}
                  <span
                    aria-hidden
                    className={`pointer-events-none absolute inset-0 bg-oxford opacity-0 transition-opacity duration-[420ms] ${EASE} group-hover:opacity-[0.04]`}
                  />
                  <span className="relative flex items-baseline justify-between">
                    <span className="type-label-section">
                      On the desk
                    </span>
                    <span
                      className={`type-action transition-[transform,color] duration-300 ${EASE} group-hover:translate-x-[2px] group-hover:text-oxford/80`}
                    >
                      Flow →
                    </span>
                  </span>
                  <span className="relative mt-phi-4 block divide-y divide-oxford/[0.06]">
                    {attention.map((s) => {
                      const reason = getDealAttentionReason(s);
                      const urgent = Boolean(s.partner?.human_review_required);
                      return (
                        <span key={s.id} className="flex flex-col gap-phi-1 py-phi-3 sm:flex-row sm:items-baseline sm:justify-between sm:gap-phi-4">
                          <span className="type-display truncate text-[15px] font-medium leading-snug text-oxford">
                            {s.scout.name}
                          </span>
                          <span
                            className={`type-meta tabular-nums sm:shrink-0 ${
                              urgent ? 'text-escalation/90' : 'text-oxford/60'
                            }`}
                          >
                            {reason}
                          </span>
                        </span>
                      );
                    })}
                  </span>
                  {attentionOverflow > 0 && (
                    <span className="type-meta relative mt-phi-2 block tabular-nums">
                      + {attentionOverflow} more
                    </span>
                  )}
                </button>
              </Reveal>
            )}

            {/* ── Two quiet doors ── */}
            <div className="mt-phi-6 w-full max-w-[46rem] border-y border-oxford/[0.12]">
              <div
                className="grid grid-cols-2 divide-x divide-oxford/[0.08]"
                role="navigation"
                aria-label="Workspaces"
              >
                <HomeDoor
                  numeral="III"
                  label="Portfolio"
                  detail={`${convictionCount} conviction · ${watchTotal} watching`}
                  index={0}
                  onClick={() => navigate('/v1/portfolio')}
                />
                <HomeDoor
                  numeral="IV"
                  label="Fund"
                  detail={
                    mandateVersion != null
                      ? `Mandate v${mandateVersion}${mandateAmended ? ` · amended ${mandateAmended}` : ''}`
                      : 'No mandate'
                  }
                  index={1}
                  onClick={() => navigate('/v1/fund')}
                />
              </div>
            </div>
          </>
        )}

        {/* ── The footer bar — Dispatch's micro-action language ── */}
        <Reveal delay={0.36} className="mt-phi-7">
          <div className="flex flex-wrap items-center justify-center gap-x-1 gap-y-1">
            <span className="type-action border-b border-oxford/10 px-1 pb-0.5">
              {displayName}
            </span>
            {fundName || mandateVersion != null ? (
              <>
                <span className="type-meta px-1 text-oxford/20" aria-hidden>·</span>
                <Link
                  to="/v1/fund"
                  className="type-action border-b border-oxford/10 px-1 pb-0.5 transition-colors hover:text-oxford btn-interaction"
                >
                  {fundName || `Mandate v${mandateVersion}`}
                </Link>
              </>
            ) : null}
            <span className="type-meta px-1 text-oxford/20" aria-hidden>·</span>
            <button
              type="button"
              onClick={openDispatch}
              className="type-action border-b border-oxford/10 px-1 pb-0.5 transition-colors hover:text-oxford btn-interaction"
            >
              {dispatchActive ? 'Lookup running' : 'Dispatch ⌘K'}
            </button>
            <span className="type-meta px-1 text-oxford/20" aria-hidden>·</span>
            <Link
              to="/v1/settings"
              className="type-action border-b border-oxford/10 px-1 pb-0.5 transition-colors hover:text-oxford btn-interaction"
            >
              Settings
            </Link>
            <span className="type-meta px-1 text-oxford/20" aria-hidden>·</span>
            <button
              type="button"
              onClick={requestLogout}
              disabled={agentActionPending}
              className="type-action border-b border-oxford/10 px-1 pb-0.5 transition-colors hover:text-oxford disabled:opacity-50 btn-interaction"
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
