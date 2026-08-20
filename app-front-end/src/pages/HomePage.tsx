import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { motion } from 'framer-motion';
import Reveal from '../components/Reveal';
import { useAppFrame } from '../components/AppFrame';
import AgentLogoutModal from '../components/AgentLogoutModal';
import { useAgentLogoutFlow } from '../hooks/useAgentLogoutFlow';
import type { ActivitySummary } from '../api/activity';
import { useCountUp, usePrefersReducedMotion } from '../hooks';
import type { SpinePipelineState } from '../components/AppSpine';
import { deriveMandatePrompt, useFundReadiness } from '../hooks/useFundReadiness';
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

/** A door — one entry in the editorial nav band. Label and a quiet reading. */
function HomeDoor({
  label,
  detail,
  tone = 'default',
  index,
  onClick,
}: {
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
            : 'text-oxford/50 group-hover:text-oxford'
        }`}
      >
        {detail}
      </span>
    </motion.button>
  );
}

/**
 * The spine's PIPELINE_TONE restated in paper values. The front door hides the
 * spine, so this is the only place the operator can see whether the pipeline is
 * actually running — it has to stay honest, especially about 'Issue'.
 */
const PIPELINE_PAPER_TONE: Record<SpinePipelineState, { dot: string; text: string }> = {
  Live: { dot: 'bg-oxford signal-dot-breathe', text: 'text-oxford/50' },
  Idle: { dot: 'bg-oxford/35', text: 'text-oxford/50' },
  Off: { dot: 'bg-oxford/[0.18]', text: 'text-oxford/50' },
  Stopping: { dot: 'bg-oxford/40 pulse-soft', text: 'text-oxford/50' },
  Issue: { dot: 'bg-escalation escalation-dot-active', text: 'text-escalation' },
};

/**
 * The pipeline readout. role="status" so a state change is announced; when the
 * pipeline is in trouble it becomes the route to fixing it, as the spine does.
 */
function PipelineIndicator({ state }: { state: SpinePipelineState }) {
  const tone = PIPELINE_PAPER_TONE[state];
  const dot = <span aria-hidden className={`h-1.5 w-1.5 shrink-0 rounded-none ${tone.dot}`} />;

  // role="status" lives on the wrapper, never on the Link — it would override
  // the link role and stop the issue route being announced as navigable.
  return (
    <span role="status" className={`inline-flex items-center ${tone.text}`}>
      {state === 'Issue' ? (
        <Link
          to="/v1/settings"
          className="inline-flex items-center gap-phi-2 btn-interaction transition-opacity hover:opacity-80"
        >
          {dot}
          Pipeline issue
        </Link>
      ) : (
        <span className="inline-flex items-center gap-phi-2">
          {dot}
          Pipeline {state.toLowerCase()}
        </span>
      )}
    </span>
  );
}

/**
 * Home — the front door as a briefing. One centered column on paper: the mark,
 * the situation spoken in serif with a since-you-left digest, the few deals on
 * the desk (the door to Flow), and two quiet doors to Portfolio and Fund.
 * Content doubles as navigation; the type and the hairlines do the work.
 */
export default function HomePage({ data, sinceAway }: { data: SystemData; sinceAway: ActivitySummary | null }) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { openDispatch, dispatchActive, pipelineState, pipelineStateReady } = useAppFrame();
  // What the agents did since the last visit (marks the report seen; null when
  // the login screen already presented it or nothing happened).
  const {
    displayName,
    agentActionPending,
    requestLogout,
    logoutModalProps,
  } = useAgentLogoutFlow();
  const { mandatePublished, unknown: fundReadinessUnknown, loading: fundReadinessLoading } = useFundReadiness();
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

  // The counts settle on mount and re-settle whenever the SSE stream lands a
  // change, so the readings visibly move as the agents work.
  const totalUp = useCountUp(startups.length);
  const openUp = useCountUp(openCount);
  const convictionUp = useCountUp(convictionCount);

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
  // flash for returning users. An unreadable readiness check is not treated
  // as a missing mandate or a published mandate.
  const mandatePrompt = deriveMandatePrompt({
    hasActiveThesis: Boolean(data.fundThesisRuntime?.active_version_id),
    mandatePublished,
    unknown: fundReadinessLoading
      || fundReadinessUnknown
      || data.fundThesisRuntimeLoading
      || Boolean(data.fundThesisRuntimeError),
  });
  const showFirstRun = mandatePrompt === 'missing';
  const showPublishPrompt = mandatePrompt === 'publish';
  const showFundReadinessUnavailable = mandatePrompt === 'unavailable';

  return (
    <div className="paper-dot-grid relative flex h-full min-h-0 flex-col overflow-y-auto overscroll-contain">
      {/* sm:px-phi-7 (55px) clears the focus-frame brackets, which reach 40px
          past the framed body; px-phi-6 (34px) would not. */}
      <div className="flex min-h-full w-full flex-1 flex-col items-center justify-center px-phi-6 py-phi-7 sm:px-phi-7">
        {/* ── The mark ── */}
        <Reveal delay={0.02} y={-6}>
          <p className="text-center font-wordmark text-[clamp(18px,1.45vw,23px)] font-medium leading-tight text-oxford">
            Aethria<span className="wordmark-dot">.</span>
          </p>
        </Reveal>

        {/* ── The dateline + pipeline readout. No rule — the headline carries the page. ── */}
        <Reveal delay={0.1} className="mt-phi-7 w-full max-w-[42rem]">
          <p className="type-label-section text-oxford/50 flex flex-wrap items-center justify-center gap-x-phi-3 gap-y-phi-1 tabular-nums">
            <span>{eyebrow}</span>
            {/* Only mounted once ready — the line is centre-justified, so the
                dateline stays visually centered while pipeline status is
                unresolved, at the cost of a small shift once it appears. */}
            {pipelineStateReady && (
              <span className="inline-flex items-center gap-x-phi-3">
                <span aria-hidden className="text-oxford/20">·</span>
                <PipelineIndicator state={pipelineState} />
              </span>
            )}
          </p>
        </Reveal>

        {/* ── The framed briefing — the login page's bracket move ── */}
        <div className="focus-frame mt-phi-4 flex w-full max-w-[42rem] flex-col items-center">
        {showFundReadinessUnavailable ? (
          <>
            <Reveal delay={0.16} y={10} className="mt-phi-6">
              <h1 className="type-display m-0 max-w-[22ch] text-center text-[clamp(24px,3.2vw,38px)] font-normal leading-[1.08] tracking-[-0.01em] text-oxford">
                Reading the mandate.
              </h1>
            </Reveal>
            <Reveal delay={0.24} className="mt-phi-5">
              <p className="type-note text-center text-oxford/65">
                Aethria could not verify fund readiness. Retry when the control plane is available.
              </p>
            </Reveal>
          </>
        ) : showFirstRun ? (
          <>
            <Reveal delay={0.16} y={10} className="mt-phi-6">
              <h1 className="type-display m-0 max-w-[22ch] text-center text-[clamp(24px,3.2vw,38px)] font-normal leading-[1.08] tracking-[-0.01em] text-oxford">
                Define your mandate.
              </h1>
            </Reveal>

            <Reveal delay={0.24} className="mt-phi-5">
              <p className="type-note text-center text-oxford/65">
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
        ) : showPublishPrompt ? (
          <>
            <Reveal delay={0.16} y={10} className="mt-phi-6">
              <h1 className="type-display m-0 max-w-[22ch] text-center text-[clamp(24px,3.2vw,38px)] font-normal leading-[1.08] tracking-[-0.01em] text-oxford">
                Publish your mandate.
              </h1>
            </Reveal>

            <Reveal delay={0.24} className="mt-phi-5">
              <p className="type-note text-center text-oxford/65">
                Aethria has a saved thesis, but it is not published as the live mandate yet.
              </p>
            </Reveal>

            <Reveal delay={0.32} className="mt-phi-7">
              <Link
                to="/v1/settings"
                className="type-action border-b border-oxford/30 px-1 pb-0.5 transition-colors hover:text-oxford btn-interaction"
              >
                Review and publish →
              </Link>
            </Reveal>
          </>
        ) : (
          <>
            <Reveal delay={0.16} y={10} className="mt-phi-6">
              <h1 className="type-display m-0 max-w-[22ch] text-center text-[clamp(24px,3.2vw,38px)] font-normal leading-[1.08] tracking-[-0.01em] text-oxford">
                {headline}
              </h1>
            </Reveal>

            <Reveal delay={0.24} className="mt-phi-5">
              <p className="type-meta text-oxford/50 flex flex-wrap items-center justify-center gap-x-phi-3 gap-y-phi-1 text-center tabular-nums">
                <span>{totalUp.toLocaleString()} in pipeline</span>
                <span aria-hidden className="text-oxford/20">·</span>
                <span>{openUp.toLocaleString()} open</span>
                {convictionCount > 0 && (
                  <>
                    <span aria-hidden className="text-oxford/20">·</span>
                    <span>{convictionUp.toLocaleString()} conviction</span>
                  </>
                )}
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
                  className={`group relative block w-full overflow-hidden px-phi-2 py-phi-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-oxford/30`}
                >
                  {/* The same whisper of oxford tint as the doors. */}
                  <span
                    aria-hidden
                    className={`pointer-events-none absolute inset-0 bg-oxford opacity-0 transition-opacity duration-[420ms] ${EASE} group-hover:opacity-[0.04]`}
                  />
                  <span className="relative flex items-baseline justify-between border-b border-oxford/[0.1] pb-phi-2">
                    <span className="type-label-section text-oxford/50">
                      On the desk
                    </span>
                    <span
                      className={`type-action text-oxford/60 transition-[transform,color] duration-300 ${EASE} group-hover:translate-x-[2px] group-hover:text-oxford/80`}
                    >
                      Flow →
                    </span>
                  </span>
                  <span className="relative mt-phi-3 block divide-y divide-oxford/[0.04]">
                    {attention.map((s) => {
                      const reason = getDealAttentionReason(s);
                      const urgent = Boolean(s.partner?.human_review_required);
                      return (
                        <span key={s.id} className="flex flex-col gap-phi-1 py-phi-3 sm:flex-row sm:items-baseline sm:justify-between sm:gap-phi-4">
                          <span className="type-display truncate text-[19px] font-medium leading-snug text-oxford">
                            {s.scout.name}
                          </span>
                          <span
                            className={`type-meta tabular-nums sm:shrink-0 ${
                              urgent ? 'text-escalation/80' : 'text-oxford/50'
                            }`}
                          >
                            {reason}
                          </span>
                        </span>
                      );
                    })}
                  </span>
                  {attentionOverflow > 0 && (
                    <span className="type-meta relative mt-phi-2 block tabular-nums text-oxford/45">
                      + {attentionOverflow} more
                    </span>
                  )}
                </button>
              </Reveal>
            )}

            {/* ── Two quiet doors ── */}
            <div className="mt-phi-6 w-full max-w-[46rem]">
              <div
                className="grid grid-cols-2 divide-x divide-oxford/[0.08]"
                role="navigation"
                aria-label="Workspaces"
              >
                <HomeDoor
                  label="Portfolio"
                  detail={`${convictionCount} conviction · ${watchTotal} watching`}
                  index={0}
                  onClick={() => navigate('/v1/portfolio')}
                />
                <HomeDoor
                  label="Fund"
                  detail={
                    mandateVersion != null
                      ? `${fundName || 'Mandate'} · v${mandateVersion}${mandateAmended ? ` · amended ${mandateAmended}` : ''}`
                      : fundName || 'No mandate'
                  }
                  index={1}
                  onClick={() => navigate('/v1/fund')}
                />
              </div>
            </div>
          </>
        )}
        </div>

        {/* ── The footer — identity, quiet, then the few actions, quieter still ── */}
        <Reveal delay={0.36} className="mt-phi-7 flex flex-col items-center gap-phi-2">
          <p className="type-meta text-oxford/35">Signed in as {displayName}</p>
          <div className="flex flex-wrap items-center justify-center gap-x-phi-3 gap-y-1">
            <button
              type="button"
              onClick={openDispatch}
              className="type-action text-oxford/50 transition-colors hover:text-oxford btn-interaction"
            >
              {dispatchActive ? 'Lookup running' : 'Dispatch ⌘K'}
            </button>
            <span aria-hidden className="text-oxford/20">·</span>
            <Link
              to="/v1/settings"
              className="type-action text-oxford/50 transition-colors hover:text-oxford btn-interaction"
            >
              Settings
            </Link>
            <span aria-hidden className="text-oxford/20">·</span>
            <button
              type="button"
              onClick={requestLogout}
              disabled={agentActionPending}
              className="type-action text-oxford/50 transition-colors hover:text-oxford disabled:opacity-50 btn-interaction"
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
