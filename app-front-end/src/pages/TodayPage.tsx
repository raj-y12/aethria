import { useEffect, useMemo } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import DecisionBadge from '../components/DecisionBadge';
import { getDecisionBadgeVariant } from '../lib/decisionBadgeVariant';
import { isDealHumanResolved, isDealUnresolved } from '../lib/dealState';
import { useSinceAwaySummary } from '../hooks/useActivitySummary';
import type { SystemData } from '../hooks/useSystemData';
import type { Startup, SignalItem } from '../types/startup';

const DAY_MS = 24 * 60 * 60 * 1000;

function daysWaiting(s: Startup): number | null {
  const since =
    s.unresolved_at ??
    s.timestamps?.unresolved_at ??
    s.timestamps?.partnered_at ??
    s.timestamps?.reviewed_at ??
    s.timestamps?.discovered_at ??
    null;
  if (!since) return null;
  const ms = Date.now() - new Date(since).getTime();
  return Number.isFinite(ms) ? Math.max(0, Math.floor(ms / DAY_MS)) : null;
}

function judgedAt(s: Startup): string {
  return (
    s.human_resolution?.resolved_at ??
    s.timestamps?.partnered_at ??
    s.timestamps?.reviewed_at ??
    ''
  );
}

function signalWhen(sig: SignalItem): string {
  if (!sig.detected_at) return '—';
  return new Date(sig.detected_at).toLocaleDateString('en-GB');
}

function SectionHead({ title, action }: { title: string; action?: { label: string; href: string } }) {
  return (
    <div className="flex items-baseline justify-between gap-phi-4 border-t border-oxford/[0.075] pt-phi-4">
      <h2 className="type-label-section text-oxford/72">{title}</h2>
      {action ? (
        <Link
          to={action.href}
          className="type-meta uppercase tracking-[0.1em] text-oxford/40 transition-colors hover:text-oxford btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
        >
          {action.label}
        </Link>
      ) : null}
    </div>
  );
}

function QuietEmpty({ children }: { children: React.ReactNode }) {
  return <p className="mt-phi-4 type-body-sm text-oxford/45">{children}</p>;
}

function DeskRow({
  onClick,
  primary,
  secondary,
  right,
}: {
  onClick: () => void;
  primary: string;
  secondary?: string;
  right?: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center justify-between gap-phi-4 border-b border-oxford/[0.06] py-phi-3 text-left transition-colors hover:bg-registerTint btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
    >
      <span className="min-w-0">
        <span className="block truncate type-body-emphasis text-oxford">{primary}</span>
        {secondary ? <span className="block truncate type-meta text-oxford/45">{secondary}</span> : null}
      </span>
      {right ? <span className="flex shrink-0 items-center gap-phi-3">{right}</span> : null}
    </button>
  );
}

/**
 * Today — the desk. The arrival surface: what requires judgment, what arrived,
 * what the instrument just ruled, and what is moving against the book. A
 * briefing, not a dashboard — every line is a doorway into the workspace
 * where the work happens.
 */
export default function TodayPage({ data }: { data: SystemData }) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { startups, signals, metaReports } = data;
  const sinceAway = useSinceAwaySummary();

  // Legacy deep links (/v1?open=…, /v1?queue=…) now belong to Flow.
  useEffect(() => {
    if (searchParams.get('open') || searchParams.get('queue')) {
      navigate(`/v1/flow?${searchParams.toString()}`, { replace: true });
    }
  }, [searchParams, navigate]);

  const openDeal = (id: string) => navigate(`/v1/flow?open=${id}`);

  const requiresJudgment = useMemo(
    () =>
      startups
        .filter((s) => isDealUnresolved(s) && s.partner?.human_review_required === true)
        .sort((a, b) => (a.timestamps?.partnered_at ?? '').localeCompare(b.timestamps?.partnered_at ?? '')),
    [startups],
  );

  const newArrivals = useMemo(
    () =>
      startups
        .filter((s) => s.is_new_to_user)
        .sort((a, b) =>
          (b.timestamps?.first_seen_at ?? b.timestamps?.discovered_at ?? '').localeCompare(
            a.timestamps?.first_seen_at ?? a.timestamps?.discovered_at ?? '',
          ),
        ),
    [startups],
  );

  const latestJudgments = useMemo(
    () =>
      startups
        .filter((s) => Boolean(s.partner?.recommendation) || isDealHumanResolved(s))
        .sort((a, b) => judgedAt(b).localeCompare(judgedAt(a)))
        .slice(0, 6),
    [startups],
  );

  const recentSignals = (signals ?? []).slice(0, 4);
  const lastCycle = metaReports.length > 0 ? metaReports[0] : null;
  const queueDepths = data.systemHealth?.queue_depths;
  const startupNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const s of startups) if (s.scout?.name) map.set(s.id, s.scout.name);
    return map;
  }, [startups]);

  const dateLine = new Date().toLocaleDateString('en-GB', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  });

  const situation = [
    requiresJudgment.length > 0
      ? `${requiresJudgment.length} ${requiresJudgment.length === 1 ? 'matter requires' : 'matters require'} your ruling`
      : 'Nothing awaits your ruling',
    newArrivals.length > 0 ? `${newArrivals.length} new ${newArrivals.length === 1 ? 'arrival' : 'arrivals'}` : null,
    recentSignals.length > 0 ? `${signals.length} ${signals.length === 1 ? 'signal' : 'signals'} live` : null,
  ]
    .filter(Boolean)
    .join(' · ');

  return (
    <div className="page-transition-enter min-h-0 flex-1 overflow-y-auto overscroll-contain">
      <div className="mx-auto w-full max-w-[1180px] px-phi-5 pb-phi-8 pt-phi-5">
        {/* ── The situation, in one line of sight ── */}
        <header className="pb-phi-6">
          <p className="type-label-section text-oxford/45">The desk</p>
          <h1 className="mt-phi-2 type-title font-medium text-oxford">{dateLine}</h1>
          <p className="mt-phi-2 type-body-sm text-oxford/55">{situation}</p>
          {sinceAway ? (
            <p className="mt-phi-3 font-mono text-[11px] tracking-[0.04em] tabular-nums text-oxford/45">
              <span className="uppercase tracking-[0.1em] text-oxford/38">Since you were away</span>
              <span className="mx-phi-2 text-oxford/20" aria-hidden>·</span>
              <span className="font-semibold text-oxford/70">{sinceAway.found}</span> discovered
              <span className="mx-phi-2 text-oxford/20" aria-hidden>·</span>
              <span className="font-semibold text-oxford/70">{sinceAway.reviewed}</span> evaluated
              <span className="mx-phi-2 text-oxford/20" aria-hidden>·</span>
              <span className="font-semibold text-oxford/70">{sinceAway.agent_decided ?? sinceAway.decided}</span> decided
              {sinceAway.escalations > 0 ? (
                <>
                  <span className="mx-phi-2 text-oxford/20" aria-hidden>·</span>
                  <span className="font-semibold text-escalation">{sinceAway.escalations}</span>
                  <span className="text-escalation/80"> escalated</span>
                </>
              ) : null}
            </p>
          ) : null}
        </header>

        <div className="grid grid-cols-1 gap-x-phi-7 gap-y-phi-6 lg:grid-cols-[minmax(0,61.8fr)_minmax(0,38.2fr)]">
          <div className="flex min-w-0 flex-col gap-phi-6">
            {/* ── Requires judgment ── */}
            <section aria-label="Requires judgment">
              <SectionHead
                title="Requires judgment"
                action={
                  requiresJudgment.length > 0
                    ? { label: 'Open queue →', href: '/v1/flow?queue=escalated' }
                    : undefined
                }
              />
              {requiresJudgment.length === 0 ? (
                <QuietEmpty>The instrument has nothing escalated. Rulings land here when the partner defers to you.</QuietEmpty>
              ) : (
                <ul className="mt-phi-2 flex flex-col">
                  {requiresJudgment.slice(0, 6).map((s) => {
                    const days = daysWaiting(s);
                    return (
                      <li key={s.id}>
                        <DeskRow
                          onClick={() => openDeal(s.id)}
                          primary={s.scout.name}
                          secondary={[s.scout.sector, s.scout.funding_stage].filter(Boolean).join(' · ') || undefined}
                          right={
                            <span
                              className={`font-mono text-[11px] tabular-nums ${
                                days != null && days >= 3 ? 'text-escalation' : 'text-oxford/45'
                              }`}
                            >
                              {days != null ? `${days}d waiting` : '—'}
                            </span>
                          }
                        />
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            {/* ── New arrivals ── */}
            <section aria-label="New arrivals">
              <SectionHead
                title="New arrivals"
                action={
                  newArrivals.length > 0 ? { label: 'Triage →', href: '/v1/flow?queue=new' } : undefined
                }
              />
              {newArrivals.length === 0 ? (
                <QuietEmpty>No unseen companies. Scouts report against the active mandate each cycle.</QuietEmpty>
              ) : (
                <ul className="mt-phi-2 flex flex-col">
                  {newArrivals.slice(0, 6).map((s) => (
                    <li key={s.id}>
                      <DeskRow
                        onClick={() => openDeal(s.id)}
                        primary={s.scout.name}
                        secondary={[s.scout.sector, s.scout.funding_stage].filter(Boolean).join(' · ') || undefined}
                        right={
                          <span className="h-1.5 w-1.5 rounded-none bg-oxford signal-dot-breathe" aria-hidden />
                        }
                      />
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>

          <div className="flex min-w-0 flex-col gap-phi-6">
            {/* ── Latest judgments ── */}
            <section aria-label="Latest judgments">
              <SectionHead title="Latest judgments" action={{ label: 'Flow →', href: '/v1/flow' }} />
              {latestJudgments.length === 0 ? (
                <QuietEmpty>No verdicts yet. The record builds as the pipeline decides.</QuietEmpty>
              ) : (
                <ul className="mt-phi-2 flex flex-col">
                  {latestJudgments.map((s) => (
                    <li key={s.id}>
                      <DeskRow
                        onClick={() => openDeal(s.id)}
                        primary={s.scout.name}
                        secondary={
                          judgedAt(s) ? new Date(judgedAt(s)).toLocaleDateString('en-GB') : undefined
                        }
                        right={<DecisionBadge variant={getDecisionBadgeVariant(s)} />}
                      />
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {/* ── Signals ── */}
            <section aria-label="Signals">
              <SectionHead title="Signals" action={{ label: 'Portfolio →', href: '/v1/portfolio' }} />
              {recentSignals.length === 0 ? (
                <QuietEmpty>No high-priority events detected.</QuietEmpty>
              ) : (
                <ul className="mt-phi-2 flex flex-col">
                  {recentSignals.map((sig, i) => (
                    <li key={sig.id ?? i} className="border-b border-oxford/[0.06] py-phi-3">
                      <span className="flex items-baseline justify-between gap-phi-3">
                        <span className="min-w-0 truncate type-meta uppercase tracking-[0.08em] text-oxford/55">
                          {(sig.startup_id ? startupNameById.get(sig.startup_id) : null) ??
                            sig.signal_type.replace(/_/g, ' ')}
                        </span>
                        <span className="shrink-0 font-mono text-[10px] tabular-nums text-oxford/35">
                          {signalWhen(sig)}
                        </span>
                      </span>
                      {sig.description ? (
                        <span className="mt-phi-1 block type-body-sm leading-relaxed text-oxford/65">
                          {sig.description}
                        </span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {/* ── The instrument ── */}
            <section aria-label="The instrument">
              <SectionHead title="The instrument" action={{ label: 'Fund →', href: '/v1/fund' }} />
              <dl className="mt-phi-2 flex flex-col">
                <div className="flex items-baseline justify-between gap-phi-3 border-b border-oxford/[0.06] py-phi-2">
                  <dt className="type-meta uppercase tracking-[0.1em] text-oxford/45">Awaiting review</dt>
                  <dd className="font-mono text-[12px] tabular-nums text-oxford/70">{queueDepths?.unreviewed ?? '—'}</dd>
                </div>
                <div className="flex items-baseline justify-between gap-phi-3 border-b border-oxford/[0.06] py-phi-2">
                  <dt className="type-meta uppercase tracking-[0.1em] text-oxford/45">Awaiting partner</dt>
                  <dd className="font-mono text-[12px] tabular-nums text-oxford/70">{queueDepths?.undecided ?? '—'}</dd>
                </div>
                <div className="flex items-baseline justify-between gap-phi-3 border-b border-oxford/[0.06] py-phi-2">
                  <dt className="type-meta uppercase tracking-[0.1em] text-oxford/45">Last correction cycle</dt>
                  <dd className="font-mono text-[12px] tabular-nums text-oxford/70">
                    {lastCycle ? new Date(lastCycle.ran_at).toLocaleDateString('en-GB') : 'Not yet run'}
                  </dd>
                </div>
                <div className="flex items-baseline justify-between gap-phi-3 border-b border-oxford/[0.06] py-phi-2">
                  <dt className="type-meta uppercase tracking-[0.1em] text-oxford/45">Mandate</dt>
                  <dd className="font-mono text-[12px] tabular-nums text-oxford/70">
                    {data.fundThesisRuntime?.active_version_number != null
                      ? `v${data.fundThesisRuntime.active_version_number} active`
                      : 'Not configured'}
                  </dd>
                </div>
              </dl>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
