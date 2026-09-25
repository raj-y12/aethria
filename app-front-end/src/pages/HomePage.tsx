import { useEffect, useMemo } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { motion } from 'framer-motion';
import Reveal from '../components/Reveal';
import { WorkspaceGlyph } from '../components/SystemBar';
import { useAppFrame } from '../components/AppFrame';
import AgentLogoutModal from '../components/AgentLogoutModal';
import { useAgentLogoutFlow } from '../hooks/useAgentLogoutFlow';
import type { ActivitySummary } from '../api/activity';
import { useCountUp, usePrefersReducedMotion } from '../hooks';
import { deriveMandatePrompt, useFundReadiness } from '../hooks/useFundReadiness';
import { transitionOrReduced } from '../design-system/motion';
import { tokens } from '../design-system/tokens';
import { getDeskAttention, isDealUnresolved } from '../lib/dealState';
import type { SystemData } from '../hooks/useSystemData';
import './HomePage.css';

/** A quiet workspace button with restrained color and width feedback. */
const EASE = 'ease-[cubic-bezier(0.16,1,0.3,1)]';

/** A door — one quiet entry in the editorial nav band. */
function HomeDoor({
  label,
  index,
  onClick,
}: {
  label: string;
  index: number;
  onClick: () => void;
}) {
  const reduceMotion = usePrefersReducedMotion();

  return (
    <motion.button
      type="button"
      onClick={onClick}
      aria-label={`${label}.`}
      initial={reduceMotion ? false : { opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={transitionOrReduced(reduceMotion, {
        duration: tokens.motion.duration.micro,
        ease: tokens.motion.ease,
        delay: 0.18 + index * 0.04,
      })}
      data-nav-label={label}
      className="aethria-home__workspace-card group relative flex items-center justify-between gap-phi-3 overflow-hidden px-phi-5 py-phi-5 text-oxford focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
    >
      {/* A whisper of Oxford tint marks the hovered cell. */}
      <span
        aria-hidden
        className={`pointer-events-none absolute inset-0 z-0 bg-oxford opacity-0 transition-opacity duration-[420ms] ${EASE} group-hover:opacity-[0.04]`}
      />
      <span className="relative z-10 flex flex-col items-center gap-phi-2">
        <span className="aethria-home__workspace-circle">
          <WorkspaceGlyph label={label} />
        </span>
        <span className={`aethria-home__workspace-label type-action type-action-strong block transition-colors duration-300 ${EASE} group-hover:text-oxford`}>
          {label}
        </span>
      </span>
    </motion.button>
  );
}

/**
 * Home — the front door as a briefing. One centered column on paper: the mark,
 * the situation spoken in serif, the few deals on the desk (the door to Flow),
 * and three focused workspace actions at the bottom.
 * Content doubles as navigation; the type and the quiet geometry do the work.
 */
export default function HomePage({ data, sinceAway: _sinceAway }: { data: SystemData; sinceAway: ActivitySummary | null }) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { openDispatch, pipelineState } = useAppFrame();
  // What the agents did since the last visit (marks the report seen; null when
  // the login screen already presented it or nothing happened).
  const { agentActionPending, requestLogout, logoutModalProps } = useAgentLogoutFlow();
  const reduceMotion = usePrefersReducedMotion();
  const { mandatePublished, unknown: fundReadinessUnknown, loading: fundReadinessLoading } = useFundReadiness();
  const { startups } = data;

  // Legacy deep links (/v1?open=…, /v1?queue=…) belong to Flow.
  useEffect(() => {
    if (searchParams.get('open') || searchParams.get('queue')) {
      navigate(`/v1/flow?${searchParams.toString()}`, { replace: true });
    }
  }, [searchParams, navigate]);

  // ── The situation ──────────────────────────────────────────────────────────
  const needRuling = data.pendingEscalationCount ?? 0;
  const newCount = useMemo(() => startups.filter((s) => s.is_new_to_user).length, [startups]);
  const openCount = useMemo(() => startups.filter(isDealUnresolved).length, [startups]);

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
  const openUp = useCountUp(openCount);

  // ── The briefing ───────────────────────────────────────────────────────────
  const attention = useMemo(() => getDeskAttention(startups), [startups]);

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
    <div className="aethria-atmosphere desk-home aethria-home grain-home relative flex h-full min-h-0 flex-col overflow-y-auto overscroll-contain">
      <div className="grain" aria-hidden="true" />
      {/* Keep enough horizontal breathing room for the bracket frame at every
          desktop width while allowing the content to use the full viewport. */}
      <div className="desk-home__inner aethria-atmosphere__inner flex min-h-full w-full flex-1 flex-col items-center justify-center px-phi-6 py-phi-7 sm:px-phi-7">
        {/* ── The framed briefing — the login page's bracket move ── */}
        <div className="desk-home__briefing focus-frame flex w-full max-w-[42rem] flex-col items-center">
        <Reveal delay={0.02} className="desk-home__brand">
          <p className="text-center font-wordmark text-[clamp(20px,1.6vw,25px)] font-medium leading-tight text-oxford">
            Aethria<span className="wordmark-dot">.</span>
          </p>
        </Reveal>
        <Reveal delay={0.1} className="desk-home__date">
          <p className="type-label-section text-oxford/55 flex flex-wrap items-center justify-center gap-x-phi-3 gap-y-phi-1 tabular-nums">
            <span>{new Intl.DateTimeFormat(undefined, { dateStyle: 'long' }).format(new Date())}</span>
          </p>
        </Reveal>
        {showFundReadinessUnavailable ? (
          <>
            <Reveal delay={0.16} y={10} className="mt-phi-6">
              <h1 data-testid="home-briefing" className="type-display m-0 max-w-[16ch] text-left text-[clamp(36px,5vw,62px)] font-semibold leading-[1.02] tracking-[-0.025em] text-oxford">
                Reading the mandate.
              </h1>
            </Reveal>
            <Reveal delay={0.24} className="mt-phi-5">
              <p className="type-note text-left text-oxford/65">
                Aethria could not verify fund readiness. Retry when the control plane is available.
              </p>
            </Reveal>
          </>
        ) : showFirstRun ? (
          <>
            <Reveal delay={0.16} y={10} className="mt-phi-6">
              <h1 data-testid="home-briefing" className="type-display m-0 max-w-[16ch] text-left text-[clamp(36px,5vw,62px)] font-semibold leading-[1.02] tracking-[-0.025em] text-oxford">
                Define your mandate.
              </h1>
            </Reveal>

            <Reveal delay={0.24} className="mt-phi-5">
              <p className="type-note text-left text-oxford/65">
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
              <h1 className="type-display m-0 max-w-[22ch] text-left text-[clamp(24px,3.2vw,38px)] font-normal leading-[1.08] tracking-[-0.01em] text-oxford">
                Publish your mandate.
              </h1>
            </Reveal>

            <Reveal delay={0.24} className="mt-phi-5">
              <p className="type-note text-left text-oxford/65">
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
        ) : null}
        {!showFundReadinessUnavailable && !showFirstRun && !showPublishPrompt ? (
          <Reveal delay={0.18} className="desk-home__flow-context">
            <h1 data-testid="home-briefing" className="type-display m-0 text-center text-[clamp(25px,3.2vw,38px)] font-medium leading-[1.08] tracking-[-0.025em] text-oxford">
              {headline}
            </h1>
            <p className="type-meta mt-phi-2 text-center text-oxford/55 tabular-nums" role="status">
              {openUp.toLocaleString()} open in the docket · Pipeline {pipelineState.toLowerCase()}
            </p>
          </Reveal>
        ) : null}
        {attention.length > 0 && !showFundReadinessUnavailable && !showFirstRun && !showPublishPrompt ? (
          <Reveal delay={0.34} className="desk-home__attention-section">
            <span className="aethria-cta-frame">
              <button
                type="button"
                onClick={() => navigate('/v1/flow')}
                aria-label={`Open Flow. ${headline}`}
                className="aethria-cta type-action"
              >
                Open Flow <span aria-hidden>→</span>
              </button>
            </span>
          </Reveal>
        ) : null}

        {!showFundReadinessUnavailable && !showFirstRun && !showPublishPrompt ? (
          <section className="desk-home__workspaces" aria-label="Workspaces">
            <p className="type-label-section text-oxford/50">Workspaces</p>
            <div className="mt-phi-3 grid grid-cols-3 gap-phi-3" role="navigation" aria-label="Workspaces">
              <HomeDoor
                label="Dispatch"
                index={0}
                onClick={openDispatch}
              />
              <HomeDoor
                label="Portfolio"
                index={1}
                onClick={() => navigate('/v1/portfolio')}
              />
              <HomeDoor
                label="Fund"
                index={2}
                onClick={() => navigate('/v1/fund')}
              />
            </div>
          </section>
        ) : null}

        </div>

      </div>

      <motion.button
        type="button"
        className="aethria-logout-float"
        aria-label="Log out"
        title="Log out"
        onClick={requestLogout}
        disabled={agentActionPending}
        transition={transitionOrReduced(reduceMotion, {
          duration: tokens.motion.duration.micro,
          ease: tokens.motion.ease,
        })}
      >
        <WorkspaceGlyph label="logout" />
      </motion.button>

      <AgentLogoutModal {...logoutModalProps} />
    </div>
  );
}
