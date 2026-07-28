import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { motion } from 'framer-motion';
import RoomHeader from '../components/RoomHeader';
import { workspaceLayout } from '../design-system/workspaceLayout';
import { usePrefersReducedMotion, useCountUp } from '../hooks';
import { usePortfolioPositions } from '../hooks/usePortfolioPositions';
import { useOutcomeCoverage } from '../hooks/useOutcomeCoverage';
import { buildPositionRows, sectorConcentration } from './portfolio/positionRows';
import OutcomePanel from '../components/institutional/OutcomePanel';
import CrmExportAction from '../components/portfolio/CrmExportAction';
import DecisionBadge from '../components/DecisionBadge';
import type { SystemData } from '../hooks/useSystemData';
import type { Startup } from '../types/startup';
import { formatDate } from '../lib/dates';

function recOf(s: Startup): string | null {
  const r = s.partner?.recommendation;
  return typeof r === 'string' && r ? r.toUpperCase() : null;
}

/** Instrument readout — a number with its label, no box. Counts up on arrival.
 * `value: null` means "unknown" (loading or failed source) — it renders an
 * em dash rather than fabricating a number. */
function Readout({ label, value, tone }: { label: string; value: number | null; tone?: 'escalation' }) {
  const shown = useCountUp(value ?? 0);
  return (
    <div className="flex flex-col gap-phi-1">
      <span
        className={`type-data text-[clamp(22px,2vw,30px)] leading-none tabular-nums ${
          tone === 'escalation' ? 'text-escalation' : 'text-oxford'
        }`}
      >
        {value == null ? '—' : shown.toLocaleString()}
      </span>
      <span className="type-label-section">{label}</span>
    </div>
  );
}

/** Group header — mono kicker + draw-in top rule, with an optional quiet
 * ghost-numeral count in the plate-num voice beside the title. */
function SectionHead({ title, detail, count }: { title: string; detail?: string; count?: number }) {
  return (
    <div className="relative flex items-baseline justify-between gap-phi-4 pt-phi-4">
      <div className="rule-draw absolute inset-x-0 top-0 h-px bg-oxford/[0.075]" aria-hidden />
      <span className="flex items-baseline gap-phi-2">
        <h2 className="type-label-section text-oxford/[0.72]">{title}</h2>
        {count != null ? (
          <span className="plate-num" aria-hidden>
            {count}
          </span>
        ) : null}
      </span>
      {detail ? <span className="type-meta tabular-nums">{detail}</span> : null}
    </div>
  );
}

function QuietEmpty({ children }: { children: React.ReactNode }) {
  return <p className="mt-phi-4 type-body-sm text-oxford/60">{children}</p>;
}

/* Outcome recording is per-position and collapsed by default — the book stays
 * readable; recording is a deliberate act. OutcomePanel resolves the canonical
 * opportunity itself from the legacy id, so positions without that bridge
 * simply cannot record yet. */
function PositionOutcomes({ startupId }: { startupId: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-phi-2">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="type-status text-oxford/55 transition-colors hover:text-oxford focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
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

/* Ledger columns (lg+): Company | Sector | Stage | Score | Ruled. Aligned cells
 * make the book comparable down the page; below lg the row falls back to the
 * stacked name + meta line. */
const LEDGER_GRID = 'lg:grid lg:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)_minmax(0,0.8fr)_60px_minmax(0,0.9fr)] lg:items-baseline lg:gap-phi-4';

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

  const positionsQuery = usePortfolioPositions();
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

  const coverageQuery = useOutcomeCoverage();
  const coveragePct = useMemo(() => {
    const raw = Number(coverageQuery.data?.coverage_ratio ?? coverageQuery.data?.coverage_rate ?? 0);
    return Math.round(raw <= 1 ? raw * 100 : raw);
  }, [coverageQuery.data]);
  /* Unknown must never read as zero — a failed or unsettled request has no
   * number to show, so the readout falls back to a dash rather than fabricating "0%". */
  const coverageUnavailable = coverageQuery.isLoading || coverageQuery.isError || !coverageQuery.data;
  const concentration = useMemo(() => sectorConcentration(rows), [rows]);

  const watchlistEntries = data.watchlistAnalytics.entries ?? [];

  return (
    <div className="page-transition-enter min-h-0 flex-1 overflow-y-auto overscroll-contain">
      <div className={`${workspaceLayout.shell} ${workspaceLayout.pageTop} ${workspaceLayout.pageBottom}`}>
        {/* ── Header: place + book composition in one line of sight ── */}
        <RoomHeader
          className={workspaceLayout.headerBottom}
          eyebrow="Conviction"
          title="Portfolio"
          readouts={
            <div className="flex flex-wrap items-end gap-x-phi-7 gap-y-phi-4">
              <Readout label="Held" value={heldUnavailable ? null : rows.length} />
              <Readout label="Monitoring" value={decided.monitoring} />
              <Readout label="Passed" value={decided.passed} />
            </div>
          }
        />

        <div className="grid grid-cols-1 gap-x-phi-7 gap-y-phi-6 lg:grid-cols-[minmax(0,61.8fr)_minmax(0,38.2fr)]">
          {/* ── Decision ledger (the record) ── */}
          <div className="flex min-w-0 flex-col gap-phi-6">
            <section aria-label="Decision ledger">
              <SectionHead title="Held" detail={`${rows.length} ${rows.length === 1 ? 'position' : 'positions'}`} />

              {/* Pointer, not a worklist — ruling happens in Flow, the book only points there. */}
              {decided.awaiting > 0 ? (
                <button
                  type="button"
                  onClick={() => navigate('/v1/flow')}
                  className="group mt-phi-3 inline-flex items-center gap-phi-2 type-body-sm text-oxford/60 transition-colors hover:text-oxford focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
                >
                  <span className="type-data tabular-nums text-oxford">{decided.awaiting}</span>
                  <span>awaiting your ruling — rule in Flow</span>
                  <span aria-hidden className="transition-transform duration-200 group-hover:translate-x-[2px]">→</span>
                </button>
              ) : null}

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
                <ul className="mt-phi-4 flex flex-col">
                  {rows.map((row) => (
                    <li key={row.position.position_id} data-testid="position-row" className="border-b border-oxford/[0.06] py-phi-3">
                      <div className={LEDGER_GRID}>
                        <span className="min-w-0">
                          <span className="block truncate type-body-emphasis text-oxford">{row.name}</span>
                          <span className="block truncate type-meta text-oxford/60 lg:hidden">
                            {[row.sector, row.stage].filter(Boolean).join(' · ') || '—'}
                          </span>
                        </span>
                        <span className="hidden min-w-0 truncate type-meta text-oxford/60 lg:block">{row.sector ?? '—'}</span>
                        <span className="hidden min-w-0 truncate type-meta text-oxford/60 lg:block">{row.stage ?? '—'}</span>
                        <span className="type-data shrink-0 text-right text-oxford/70">
                          {row.score == null ? '—' : row.score.toFixed(1)}
                        </span>
                        <span className="type-meta hidden shrink-0 truncate text-right text-oxford/60 lg:block">
                          {new Date(row.position.entered_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                        </span>
                      </div>
                      <p className="mt-phi-2 type-body-sm leading-relaxed text-oxford/70">{row.position.entry_rationale}</p>
                      {row.startupId ? <PositionOutcomes startupId={row.startupId} /> : null}
                      <CrmExportAction opportunityId={row.position.opportunity_id} companyName={row.name} />
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section aria-label="Decision history">
              <SectionHead
                title="Decision history"
                detail={`${decisionHistory.length} resolved`}
              />
              {decisionHistory.length === 0 ? (
                <QuietEmpty>No monitoring or passed decisions yet.</QuietEmpty>
              ) : (
                <ul className="mt-phi-4 flex flex-col">
                  {decisionHistory.map((item) => (
                    <li key={item.startup.id} className="border-b border-oxford/[0.06]">
                      <button
                        type="button"
                        onClick={() => openDeal(item.startup.id)}
                        className="group flex w-full items-start justify-between gap-phi-4 py-phi-3 text-left transition-colors hover:bg-oxford/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 btn-interaction btn-interaction--no-press"
                      >
                        <span className="min-w-0">
                          <span className="block truncate type-body-emphasis text-oxford">{item.name}</span>
                          {item.notes ? (
                            <span className="mt-phi-1 block line-clamp-2 type-meta text-oxford/60">{item.notes}</span>
                          ) : null}
                        </span>
                        <span className="flex shrink-0 flex-col items-end gap-phi-1">
                          <DecisionBadge variant={item.decision === 'NO' ? 'PASS' : 'MONITOR'} />
                          <span className="type-meta tabular-nums text-oxford/55">{formatDate(item.resolvedAt)}</span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {/* ── Concentration — recomputed from the rows above, so it can never disagree with them ── */}
            <section aria-label="Sector concentration">
              <SectionHead title="Concentration" detail={concentration[0]?.sector} />
              {concentration.length === 0 ? (
                <QuietEmpty>Appears once you hold a position.</QuietEmpty>
              ) : (
                <ul className="mt-phi-4 flex flex-col gap-phi-3">
                  {concentration.map((entry, i) => (
                    <li
                      key={entry.sector}
                      data-testid={`concentration-row-${entry.sector}`}
                      className="grid grid-cols-[minmax(90px,140px)_1fr_64px] items-center gap-phi-4"
                    >
                      <span className="type-label-section truncate">{entry.sector}</span>
                      <span className="relative block h-px bg-oxford/10">
                        <motion.span
                          className="absolute inset-y-0 left-0 origin-left bg-oxford/45"
                          style={{ width: `${Math.max(2, entry.pct)}%` }}
                          initial={reduceMotion ? { scaleX: 1 } : { scaleX: 0 }}
                          animate={{ scaleX: 1 }}
                          transition={{ duration: 0.9, delay: reduceMotion ? 0 : 0.1 + i * 0.05, ease: [0.16, 1, 0.3, 1] }}
                        />
                      </span>
                      <span className="type-data text-right text-oxford/60">
                        {entry.count} · {entry.pct}%
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>

          {/* ── Watchlist + signals ── */}
          <div className="flex min-w-0 flex-col gap-phi-6">
            <section aria-label="Watchlist">
              <SectionHead
                title="Watchlist"
                detail={`${data.watchlistAnalytics.total}${data.watchlistAnalytics.stale ? ` · ${data.watchlistAnalytics.stale} stale` : ''}`}
                count={data.watchlistAnalytics.total}
              />
              {watchlistEntries.length === 0 ? (
                <QuietEmpty>Nothing held under observation.</QuietEmpty>
              ) : (
                <ul className="mt-phi-2 flex flex-col">
                  {watchlistEntries.slice(0, 20).map((e, i) => (
                    <li key={e.startup_id ?? i} className="border-b border-oxford/[0.06]">
                      <button
                        type="button"
                        onClick={() => e.startup_id && openDeal(e.startup_id)}
                        disabled={!e.startup_id}
                        className="group -mx-phi-3 flex w-[calc(100%+2*var(--space-3))] items-center justify-between gap-phi-3 px-phi-3 py-phi-2 text-left transition-colors hover:bg-oxford/[0.05] disabled:cursor-default btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
                      >
                        <span className="min-w-0 truncate type-body-sm text-oxford">
                          {e.startup_name ?? (e.startup_id ? startupNameById.get(e.startup_id) : null) ?? 'Unknown'}
                        </span>
                        <span
                          className={`type-data shrink-0 transition-colors ${
                            e.stale_warning ? 'text-escalation' : 'text-oxford/60 group-hover:text-oxford'
                          }`}
                        >
                          {e.days_on_watchlist != null ? `${e.days_on_watchlist}d` : '—'}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section aria-label="Outcome coverage">
              <SectionHead title="Outcome coverage" />
              <div className="mt-phi-4 flex flex-col gap-phi-2">
                <span className="type-data text-[clamp(22px,2vw,30px)] leading-none tabular-nums text-oxford">
                  {coverageUnavailable ? '—' : `${coveragePct}%`}
                </span>
                <span className={`type-body-sm ${coverageQuery.isError ? 'text-escalation' : 'text-oxford/65'}`}>
                  {coverageQuery.isError
                    ? 'Coverage is unavailable right now — unknown, not zero.'
                    : 'of eligible decisions have a recorded outcome.'}
                </span>
              </div>
              {(coverageQuery.data?.limitations ?? []).length > 0 ? (
                <ul className="mt-phi-3 flex flex-col gap-phi-1">
                  {coverageQuery.data?.limitations?.map((limitation) => (
                    <li key={limitation} className="type-meta text-oxford/55">{limitation}</li>
                  ))}
                </ul>
              ) : null}
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
