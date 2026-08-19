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

/** Instrument readout — a number with its label, no box. Counts up on arrival.
 * `value: null` means "unknown" (loading or failed source) — it renders an
 * em dash rather than fabricating a number. */
function Readout({ label, value, tone }: { label: string; value: number | null; tone?: 'escalation' }) {
  const shown = useCountUp(value ?? 0);
  return (
    <div className="flex flex-col gap-phi-1">
        {/* Deliberate escape from the φ type scale (hero tops at 37px) — this is
            the one "big instrument number" moment on the page, sized for its own
            emphasis rather than reused elsewhere. Not scale drift. */}
        <span
        className={`type-data !text-[clamp(32px,3.2vw,46px)] leading-none tabular-nums ${
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
  return <p className="mt-phi-4 type-body-sm text-oxford/65">{children}</p>;
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
        className="type-status text-oxford/65 transition-colors hover:text-oxford focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
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
  const topPosition = concentration[0];
  const convictionHeadline = rows.length > 0
    ? `${rows.length} conviction${rows.length === 1 ? '' : 's'}. The record of what we chose.`
    : 'The record of conviction.';

  return (
    <div className="paper-dot-grid page-transition-enter min-h-0 flex-1 overflow-y-auto overscroll-contain">
      <div className={`${workspaceLayout.shell} ${workspaceLayout.pageTop} ${workspaceLayout.pageBottom} min-h-full`}>
        <header className={`border-b border-oxford/[0.075] ${workspaceLayout.headerBottom}`}>
          <p className="type-label-section type-label-section--eyebrow">Portfolio</p>
          <h1 className="type-display mt-phi-3 max-w-[56rem] text-[clamp(30px,3vw,42px)] leading-[1.08] text-oxford">
            {convictionHeadline}
          </h1>
          <div className="mt-phi-6 flex flex-wrap items-end gap-x-phi-7 gap-y-phi-4">
            <Readout label="Held" value={heldUnavailable ? null : rows.length} />
            <Readout label="Watching" value={data.watchlistAnalytics.total} />
            <Readout label="Top position" value={topPosition?.pct ?? null} />
            <Readout label="Rulings recorded" value={decisionHistory.length} />
          </div>
        </header>

        <div className="grid grid-cols-1 gap-x-phi-8 gap-y-phi-8 pt-phi-6 lg:grid-cols-[minmax(0,1.55fr)_minmax(280px,0.8fr)]">
          {/* ── Decision ledger (the record) ── */}
          <div className="flex min-w-0 flex-col gap-phi-6">
            <section aria-label="Decision ledger">
              <SectionHead title="Positions" detail={`${rows.length} ${rows.length === 1 ? 'position' : 'positions'}`} />

              {/* Pointer, not a worklist — ruling happens in Flow, the book only points there. */}
              {decided.awaiting > 0 ? (
                <button
                  type="button"
                  onClick={() => navigate('/v1/flow')}
                  className="group mt-phi-3 inline-flex items-center gap-phi-2 type-body-sm text-oxford/65 transition-colors hover:text-oxford focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
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
                    <li key={row.position.position_id} data-testid="position-row" className="group border-b border-oxford/[0.06]">
                      <div className="-mx-phi-3 grid w-[calc(100%+2*var(--space-3))] gap-x-phi-4 gap-y-phi-2 px-phi-3 py-phi-4 text-left transition-colors hover:bg-oxford/[0.05] lg:grid-cols-[minmax(0,1.15fr)_minmax(126px,0.65fr)_minmax(0,1.5fr)] lg:items-baseline">
                        <span className="min-w-0 font-display text-[18px] font-medium leading-[1.15] tracking-[-0.01em] text-oxford">{row.name}</span>
                        <span className="flex min-w-0 flex-col items-start gap-phi-1">
                          <span className="type-meta text-oxford/65">INVESTED · {row.stage ?? 'POSITION'}</span>
                          <span className="type-meta text-oxford/65">
                            <span>{row.sector ?? 'SECTOR UNKNOWN'}</span>
                            <span aria-hidden> · </span>
                            <span>{row.score == null ? 'SCORE —' : `SCORE ${row.score.toFixed(1)}`}</span>
                          </span>
                        </span>
                        <p className="min-w-0 type-body-sm leading-relaxed text-oxford/70">{row.position.entry_rationale || 'No entry rationale recorded.'}</p>
                      </div>
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
                        className="group -mx-phi-3 grid w-[calc(100%+2*var(--space-3))] gap-x-phi-6 gap-y-phi-2 px-phi-3 py-phi-4 text-left transition-colors hover:bg-oxford/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 btn-interaction btn-interaction--no-press lg:grid-cols-[minmax(0,1.15fr)_minmax(142px,0.55fr)_minmax(0,1.5fr)] lg:items-baseline"
                      >
                        <span className="flex min-w-0 flex-col items-start gap-phi-1">
                          <span className="font-display text-[18px] font-medium leading-[1.15] tracking-[-0.01em] text-oxford">{item.name}</span>
                          <span className="type-meta tabular-nums text-oxford/65">{formatDate(item.resolvedAt)}</span>
                        </span>
                        <span className="flex min-w-0 items-center gap-phi-2" aria-label="Aethria recommendation followed by your ruling">
                          {recOf(item.startup) ? (
                            <DecisionBadge
                              variant={recOf(item.startup) as 'INVEST' | 'PASS' | 'MONITOR'}
                              className="cursor-help"
                            />
                          ) : <span className="type-meta text-oxford/65">—</span>}
                          <span className="type-meta text-oxford/65" aria-hidden>→</span>
                          <DecisionBadge
                            variant={rulingToRecommendation(item.decision)}
                            className="cursor-help"
                          />
                        </span>
                        <span className="min-w-0 type-body-sm leading-relaxed text-oxford/70">{item.notes || '—'}</span>
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
                          transition={{ duration: 0.9, delay: reduceMotion ? 0 : 0.1 + i * 0.05, ease: tokens.motion.ease }}
                        />
                      </span>
                      <span className="type-data text-right text-oxford/65">
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
                detail={data.watchlistAnalytics.stale ? `${data.watchlistAnalytics.stale} stale` : undefined}
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
                            e.stale_warning ? 'text-escalation' : 'text-oxford/65 group-hover:text-oxford'
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
                    <li key={limitation} className="type-meta text-oxford/65">{limitation}</li>
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
