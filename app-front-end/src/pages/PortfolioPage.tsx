import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { motion } from 'framer-motion';
import { useQuery } from '@tanstack/react-query';
import { workspaceLayout } from '../design-system/workspaceLayout';
import { tokens } from '../design-system/tokens';
import { usePrefersReducedMotion, useCountUp } from '../hooks';
import { fetchPortfolioPositions } from '../api/portfolio';
import { fetchOutcomeCoverage } from '../api/channelsOutcomes';
import { buildPositionRows, sectorConcentration } from './portfolio/positionRows';
import OutcomePanel from '../components/institutional/OutcomePanel';
import CrmExportAction from '../components/portfolio/CrmExportAction';
import DecisionBadge from '../components/DecisionBadge';
import SegmentedPill from '../components/SegmentedPill';
import type { SystemData } from '../hooks/useSystemData';
import type { Startup } from '../types/startup';
import { formatDate } from '../lib/dates';

function recOf(s: Startup): string | null {
  const r = s.partner?.recommendation;
  return typeof r === 'string' && r ? r.toUpperCase() : null;
}

function rulingToRecommendation(decision: 'MAYBE' | 'NO'): 'MONITOR' | 'PASS' {
  return decision === 'NO' ? 'PASS' : 'MONITOR';
}

const portfolioRowVariants = {
  hidden: { opacity: 0, y: 6 },
  visible: (index: number) => ({
    opacity: 1,
    y: 0,
    transition: {
      duration: tokens.motion.duration.short,
      delay: Math.min(index, 8) * 0.03,
      ease: tokens.motion.ease,
    },
  }),
};

/** A header reading: mono caption beside its number, set as one quiet line
 * rather than a giant numeral. `value: null` means "unknown" (loading or failed
 * source) and renders an em dash rather than fabricating a number. */
function Readout({ label, value }: { label: string; value: number | null }) {
  const shown = useCountUp(value ?? 0);
  return (
    <div className="flex items-baseline gap-phi-2">
      <span className="type-label-section">{label}</span>
      <span className="type-body-sm tabular-nums text-oxford">{value == null ? '—' : shown.toLocaleString()}</span>
    </div>
  );
}

/** A section caption — mono label with an optional right-hand detail. No rule. */
function Caption({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-phi-4">
      <h2 className="type-label-section">{title}</h2>
      {detail ? <span className="type-meta tabular-nums text-oxford/55">{detail}</span> : null}
    </div>
  );
}

const PORTFOLIO_VIEWS = [
  { key: 'held', label: 'Holdings' },
  { key: 'decided', label: 'Decided' },
] as const;
type PortfolioView = (typeof PORTFOLIO_VIEWS)[number]['key'];

function QuietEmpty({ children }: { children: React.ReactNode }) {
  return <p className="mt-phi-4 type-body-sm text-oxford/55">{children}</p>;
}

/* Outcome recording is per-position and collapsed by default — the book stays
 * readable; recording is a deliberate act. OutcomePanel resolves the canonical
 * opportunity itself from the legacy id, so positions without that bridge
 * simply cannot record yet. */
function PositionOutcomes({ startupId }: { startupId: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="type-action text-oxford/55 transition-colors hover:text-oxford focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
      >
        {open ? 'Hide outcomes' : 'Record outcome'}
      </button>
      {open ? (
        <div className="mt-phi-3">
          <OutcomePanel startupId={startupId} />
        </div>
      ) : null}
    </div>
  );
}

/**
 * Portfolio — the *record*: positions held, read from the canonical
 * `/api/portfolio/positions` endpoint, plus decision history, concentration,
 * watchlist, and signals. Active judgement still lives in Flow; this page
 * preserves what happened. Built from data the pipeline already persists; no
 * fabricated returns.
 */
export default function PortfolioPage({ data }: { data: SystemData }) {
  const navigate = useNavigate();
  const reduceMotion = usePrefersReducedMotion();
  const openDeal = (id: string) => navigate(`/v1/flow?open=${id}`);
  const [view, setView] = useState<PortfolioView>('held');

  const positionsQuery = useQuery({
    queryKey: ['portfolio-positions', 100],
    queryFn: () => fetchPortfolioPositions(100),
    staleTime: 30_000,
  });
  const rows = useMemo(
    () => buildPositionRows(positionsQuery.data ?? [], data.startups),
    [positionsQuery.data, data.startups],
  );
  /* Unknown must never read as zero — a loading or failed positions request
   * has no count to show, so "Held" falls back to a dash rather than "0". */
  const heldUnavailable = positionsQuery.isLoading || positionsQuery.isError;

  /* Decided-but-not-held is history, not holdings. Counts stay because they are
   * facts; the deals themselves live in Flow. */
  const decided = useMemo(() => {
    let monitoring = 0;
    let passed = 0;
    let awaiting = 0;
    for (const s of data.startups) {
      const decision = s.human_resolution?.decision;
      if (decision === 'MAYBE') monitoring += 1;
      else if (decision === 'NO') passed += 1;
      else if (recOf(s)) awaiting += 1;
    }
    return { monitoring, passed, awaiting };
  }, [data.startups]);

  const decisionHistory = useMemo(() => data.startups
    .filter((startup) => {
      const decision = startup.human_resolution?.decision;
      return decision === 'MAYBE' || decision === 'NO';
    })
    .map((startup) => ({
      startup,
      decision: startup.human_resolution!.decision as 'MAYBE' | 'NO',
      name: startup.scout?.name?.trim() || startup.id,
      notes: startup.human_resolution?.notes?.trim() ?? '',
      resolvedAt: startup.human_resolution?.resolved_at,
    }))
    .sort((a, b) => (b.resolvedAt ?? '').localeCompare(a.resolvedAt ?? '')),
  [data.startups]);

  const startupNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const s of data.startups) {
      if (s.scout?.name) map.set(s.id, s.scout.name);
    }
    return map;
  }, [data.startups]);

  const coverageQuery = useQuery({
    queryKey: ['outcomes', 'coverage'],
    queryFn: fetchOutcomeCoverage,
    staleTime: 60_000,
    retry: false,
  });
  const coveragePct = useMemo(() => {
    const raw = Number(coverageQuery.data?.coverage_ratio ?? coverageQuery.data?.coverage_rate ?? 0);
    return Math.round(raw <= 1 ? raw * 100 : raw);
  }, [coverageQuery.data]);
  /* Unknown must never read as zero — a failed or unsettled request has no
   * number to show, so the readout falls back to a dash rather than fabricating "0%". */
  const coverageUnavailable = coverageQuery.isLoading || coverageQuery.isError || !coverageQuery.data;
  const concentration = useMemo(() => sectorConcentration(rows), [rows]);

  const watchlistEntries = data.watchlistAnalytics.entries ?? [];
  const convictionHeadline = rows.length > 0
    ? `${rows.length} conviction${rows.length === 1 ? '' : 's'}. The record of what we chose.`
    : 'The record of conviction.';

  return (
    <div className="aethria-portfolio paper-dot-grid page-transition-enter min-h-0 flex-1 overflow-y-auto overscroll-contain">
      <div className={`${workspaceLayout.shell} ${workspaceLayout.pageTop} ${workspaceLayout.pageBottom} min-h-full`}>
        {/* The masthead: eyebrow, the record's headline, and one quiet line of
            readings. The Held/Decided switch sits top-right, as on Fund. */}
        <header className={workspaceLayout.headerBottom}>
          <div className="flex flex-wrap items-center justify-between gap-phi-4">
            <p className="type-label-section type-label-section--eyebrow">Portfolio</p>
            <SegmentedPill
              options={PORTFOLIO_VIEWS}
              value={view}
              onChange={setView}
              label="Portfolio view"
              layoutId="portfolio-view-active"
            />
          </div>
          <h1 className="type-display mt-phi-5 max-w-[22ch] text-[clamp(30px,3.2vw,44px)] font-medium leading-[1.06] text-oxford">
            {convictionHeadline}
          </h1>
          <div className="mt-phi-5 flex flex-wrap items-baseline gap-x-phi-6 gap-y-phi-2">
            <Readout label="Held" value={heldUnavailable ? null : rows.length} />
            <Readout label="Watching" value={data.watchlistAnalytics.total} />
            <Readout label="Rulings recorded" value={decisionHistory.length} />
          </div>
        </header>

        {view === 'held' ? (
          <div className="grid grid-cols-1 gap-phi-8 pt-phi-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(260px,1fr)]">
            {/* ── Positions: each holding is a soft panel, the record's hero ── */}
            <div className="flex min-w-0 flex-col gap-phi-7">
              <section aria-label="Decision ledger" className="flex flex-col gap-phi-4">
                <Caption title="Positions" detail={`${rows.length} held`} />

                {positionsQuery.isLoading ? (
                  <QuietEmpty>Loading positions…</QuietEmpty>
                ) : positionsQuery.isError ? (
                  <QuietEmpty>Positions unavailable right now. Nothing has been lost — retry shortly.</QuietEmpty>
                ) : rows.length === 0 ? (
                  <QuietEmpty>
                    No positions yet. A company becomes a position when you rule it INVEST — a
                    recommendation alone does not.
                  </QuietEmpty>
                ) : (
                  <ul className="flex flex-col gap-phi-4">
                    {rows.map((row, index) => (
                      <motion.li
                        key={row.position.position_id}
                        data-testid="position-row"
                        custom={index}
                        variants={portfolioRowVariants}
                        initial={reduceMotion ? false : 'hidden'}
                        animate="visible"
                        layout="position"
                        className="flex flex-col gap-phi-5 rounded-[18px] bg-oxford/[0.04] p-phi-5"
                      >
                        <div className="flex flex-wrap items-baseline justify-between gap-phi-3">
                          <span className="type-label-section">Held since {formatDate(row.position.entered_at)}</span>
                          <span className="flex items-baseline gap-phi-2">
                            <span className="type-label-section">{row.stage ?? 'Stage unknown'}</span>
                            <span aria-hidden className="type-label-section">·</span>
                            <span className="type-label-section">{row.sector ?? 'Sector unknown'}</span>
                          </span>
                        </div>
                        <div className="flex items-end justify-between gap-phi-5">
                          <span className="min-w-0 font-display text-[clamp(24px,2.2vw,30px)] font-medium leading-[1.05] tracking-[-0.03em] text-oxford">{row.name}</span>
                          <span className="flex shrink-0 flex-col items-end gap-phi-1">
                            <span className="type-display text-[clamp(28px,2.6vw,38px)] font-normal leading-none tabular-nums text-oxford">
                              {Math.round(row.position.investor_confidence * 100)}%
                            </span>
                            <span className="type-label-section">Confidence</span>
                          </span>
                        </div>
                        <p className="max-w-[46ch] type-body-sm leading-relaxed text-oxford/65">{row.position.entry_rationale || 'No entry rationale recorded.'}</p>
                        <div className="flex flex-wrap items-start gap-x-phi-5 gap-y-phi-2">
                          {row.startupId ? <PositionOutcomes startupId={row.startupId} /> : null}
                          <CrmExportAction opportunityId={row.position.opportunity_id} companyName={row.name} />
                        </div>
                      </motion.li>
                    ))}
                  </ul>
                )}

                {/* Pointer, not a worklist — ruling happens in Flow, the book only points there. */}
                {decided.awaiting > 0 ? (
                  <button
                    type="button"
                    onClick={() => navigate('/v1/flow')}
                    className="group inline-flex w-fit items-baseline gap-phi-2 type-body-sm text-oxford/60 transition-colors hover:text-oxford focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
                  >
                    <span className="tabular-nums text-oxford">{decided.awaiting}</span>
                    <span>awaiting your ruling in Flow</span>
                    <span aria-hidden className="transition-transform duration-200 group-hover:translate-x-[2px]">→</span>
                  </button>
                ) : null}
              </section>

              {/* ── Concentration — recomputed from the rows above, so it can never disagree with them ── */}
              <section aria-label="Sector concentration" className="flex flex-col gap-phi-4">
                <Caption title="Concentration" detail={concentration[0]?.sector} />
                {concentration.length === 0 ? (
                  <QuietEmpty>Appears once you hold a position.</QuietEmpty>
                ) : (
                  <ul className="flex flex-col gap-phi-3">
                    {concentration.map((entry, i) => (
                      <li
                        key={entry.sector}
                        data-testid={`concentration-row-${entry.sector}`}
                        className="grid grid-cols-[minmax(90px,160px)_1fr_72px] items-center gap-phi-4"
                      >
                        <span className="type-body-sm truncate text-oxford">{entry.sector}</span>
                        <span className="relative block h-[6px] overflow-hidden rounded-full bg-oxford/[0.08]">
                          <motion.span
                            className="absolute inset-y-0 left-0 origin-left rounded-full bg-oxford"
                            style={{ width: `${Math.max(2, entry.pct)}%` }}
                            initial={reduceMotion ? { scaleX: 1 } : { scaleX: 0 }}
                            animate={{ scaleX: 1 }}
                            transition={{ duration: 0.9, delay: reduceMotion ? 0 : 0.1 + i * 0.05, ease: tokens.motion.ease }}
                          />
                        </span>
                        <span className="type-meta text-right tabular-nums text-oxford/55">
                          {entry.count} · {entry.pct}%
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>

            {/* ── Watchlist + outcome coverage ── */}
            <div className="flex min-w-0 flex-col gap-phi-7">
              <section aria-label="Watchlist" className="flex flex-col gap-phi-3">
                <Caption
                  title={`Watching · ${data.watchlistAnalytics.total}`}
                  detail={data.watchlistAnalytics.stale ? `${data.watchlistAnalytics.stale} stale` : undefined}
                />
                {watchlistEntries.length === 0 ? (
                  <QuietEmpty>Nothing held under observation.</QuietEmpty>
                ) : (
                  <ul className="-mx-phi-3 flex flex-col">
                    {watchlistEntries.slice(0, 20).map((e, i) => (
                      <motion.li
                        key={e.startup_id ?? i}
                        custom={i}
                        variants={portfolioRowVariants}
                        initial={reduceMotion ? false : 'hidden'}
                        animate="visible"
                        layout="position"
                      >
                        <button
                          type="button"
                          onClick={() => e.startup_id && openDeal(e.startup_id)}
                          disabled={!e.startup_id}
                          className="group flex w-full items-center justify-between gap-phi-3 rounded-[12px] px-phi-3 py-phi-3 text-left transition-colors hover:bg-oxford/[0.04] disabled:cursor-default btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
                        >
                          <span className="min-w-0 truncate type-body-sm text-oxford">
                            {e.startup_name ?? (e.startup_id ? startupNameById.get(e.startup_id) : null) ?? 'Unknown'}
                          </span>
                          <span className={`type-meta shrink-0 tabular-nums ${e.stale_warning ? 'text-escalation' : 'text-oxford/55'}`}>
                            {e.days_on_watchlist != null ? `${e.days_on_watchlist}d` : '—'}
                          </span>
                        </button>
                      </motion.li>
                    ))}
                  </ul>
                )}
              </section>

              <section aria-label="Outcome coverage" className="flex flex-col gap-phi-3 rounded-[18px] bg-oxford/[0.04] p-phi-5">
                <span className="type-label-section">Outcome coverage</span>
                <span className="type-display text-[clamp(36px,3.2vw,48px)] font-normal leading-none tabular-nums text-oxford">
                  {coverageUnavailable ? '—' : `${coveragePct}%`}
                </span>
                <span className={`type-body-sm ${coverageQuery.isError ? 'text-escalation' : 'text-oxford/55'}`}>
                  {coverageQuery.isError
                    ? 'Coverage is unavailable right now — unknown, not zero.'
                    : 'of eligible decisions have a recorded outcome.'}
                </span>
                {(coverageQuery.data?.limitations ?? []).length > 0 ? (
                  <ul className="flex flex-col gap-phi-1">
                    {coverageQuery.data?.limitations?.map((limitation) => (
                      <li key={limitation} className="type-meta text-oxford/45">{limitation}</li>
                    ))}
                  </ul>
                ) : null}
              </section>
            </div>
          </div>
        ) : (
          /* ── Decided: monitoring and passed rulings, newest first ── */
          <section aria-label="Decision history" className="flex flex-col gap-phi-4 pt-phi-6">
            <Caption title="Decision history" detail={`${decisionHistory.length} resolved`} />
            {decisionHistory.length === 0 ? (
              <QuietEmpty>No monitoring or passed decisions yet.</QuietEmpty>
            ) : (
              <ul className="-mx-phi-3 flex flex-col">
                {decisionHistory.map((item, index) => (
                  <motion.li
                    key={item.startup.id}
                    custom={index}
                    variants={portfolioRowVariants}
                    initial={reduceMotion ? false : 'hidden'}
                    animate="visible"
                    layout="position"
                  >
                    <button
                      type="button"
                      onClick={() => openDeal(item.startup.id)}
                      className="group grid w-full gap-x-phi-6 gap-y-phi-2 rounded-[14px] px-phi-3 py-phi-4 text-left transition-colors hover:bg-oxford/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 btn-interaction btn-interaction--no-press lg:grid-cols-[minmax(0,1.1fr)_minmax(150px,0.55fr)_minmax(0,1.5fr)] lg:items-baseline"
                    >
                      <span className="flex min-w-0 flex-col items-start gap-phi-1">
                        <span className="font-display text-[20px] font-medium leading-[1.1] tracking-[-0.02em] text-oxford">{item.name}</span>
                        <span className="type-meta tabular-nums text-oxford/55">{formatDate(item.resolvedAt)}</span>
                      </span>
                      <span className="flex min-w-0 items-center gap-phi-2" aria-label="Aethria recommendation followed by your ruling">
                        {recOf(item.startup) ? (
                          <DecisionBadge
                            variant={recOf(item.startup) as 'INVEST' | 'PASS' | 'MONITOR'}
                            className="cursor-help"
                          />
                        ) : <span className="type-meta text-oxford/55">—</span>}
                        <span className="type-meta text-oxford/55" aria-hidden>→</span>
                        <DecisionBadge
                          variant={rulingToRecommendation(item.decision)}
                          className="cursor-help"
                        />
                      </span>
                      <span className="min-w-0 type-body-sm leading-relaxed text-oxford/65">{item.notes || '—'}</span>
                    </button>
                  </motion.li>
                ))}
              </ul>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
