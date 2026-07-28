import { useMemo } from 'react';
import { useNavigate } from 'react-router';
import { motion } from 'framer-motion';
import RoomHeader from '../components/RoomHeader';
import { workspaceLayout } from '../design-system/workspaceLayout';
import { usePrefersReducedMotion, useCountUp } from '../hooks';
import { usePortfolioPositions } from '../hooks/usePortfolioPositions';
import { buildPositionRows } from './portfolio/positionRows';
import type { SystemData } from '../hooks/useSystemData';
import type { Startup, SignalItem } from '../types/startup';
import { formatDateTime } from '../lib/dates';

function recOf(s: Startup): string | null {
  const r = s.partner?.recommendation;
  return typeof r === 'string' && r ? r.toUpperCase() : null;
}

/** Instrument readout — a number with its label, no box. Counts up on arrival. */
function Readout({ label, value, tone }: { label: string; value: number; tone?: 'escalation' }) {
  const shown = useCountUp(value);
  return (
    <div className="flex flex-col gap-phi-1">
      <span
        className={`type-data text-[clamp(22px,2vw,30px)] leading-none tabular-nums ${
          tone === 'escalation' ? 'text-escalation' : 'text-oxford'
        }`}
      >
        {shown.toLocaleString()}
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

function signalWhen(sig: SignalItem): string {
  return formatDateTime(sig.detected_at);
}

/* Ledger columns (lg+): Company | Sector | Stage | Score | Ruled. Aligned cells
 * make the book comparable down the page; below lg the row falls back to the
 * stacked name + meta line. */
const LEDGER_GRID = 'lg:grid lg:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)_minmax(0,0.8fr)_60px_minmax(0,0.9fr)] lg:items-baseline lg:gap-phi-4';

/**
 * Portfolio — the *record*: positions held, read from the canonical
 * `/api/portfolio/positions` endpoint, plus concentration, watchlist, and
 * signals. Monitoring/Passed are decision history, not holdings — their
 * counts stay here as facts, but the deals themselves live in Flow. Built
 * from data the pipeline already persists; no fabricated returns.
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

  const startupNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const s of data.startups) {
      if (s.scout?.name) map.set(s.id, s.scout.name);
    }
    return map;
  }, [data.startups]);

  const sectorRows = useMemo(() => {
    const entries = Object.entries(data.concentrationAnalytics.by_sector ?? {});
    return entries
      .map(([sector, v]) => ({ sector, count: v.count, pct: v.pct_of_total }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [data.concentrationAnalytics]);
  const maxSectorCount = Math.max(...sectorRows.map((r) => r.count), 1);

  const watchlistEntries = data.watchlistAnalytics.entries ?? [];
  const recentSignals = (data.signals ?? []).slice(0, 20);

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
              <Readout label="Held" value={rows.length} />
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
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {/* ── Concentration ── */}
            <section aria-label="Sector concentration">
              <SectionHead
                title="Concentration"
                detail={data.concentrationAnalytics.most_concentrated_sector || undefined}
              />
              {sectorRows.length === 0 ? (
                <QuietEmpty>Appears once deals are decided.</QuietEmpty>
              ) : (
                <ul className="mt-phi-4 flex flex-col gap-phi-3">
                  {sectorRows.map((row, i) => (
                    <li key={row.sector} className="grid grid-cols-[minmax(90px,140px)_1fr_64px] items-center gap-phi-4">
                      <span className="type-label-section truncate">{row.sector}</span>
                      <span className="relative block h-px bg-oxford/10">
                        <motion.span
                          className="absolute inset-y-0 left-0 origin-left bg-oxford/45"
                          style={{ width: `${Math.max(2, Math.min(100, (row.count / maxSectorCount) * 100))}%` }}
                          initial={reduceMotion ? { scaleX: 1 } : { scaleX: 0 }}
                          animate={{ scaleX: 1 }}
                          transition={{ duration: 0.9, delay: reduceMotion ? 0 : 0.1 + i * 0.05, ease: [0.16, 1, 0.3, 1] }}
                        />
                      </span>
                      <span className="type-data text-right text-oxford/60">
                        {row.count} · {row.pct.toFixed(0)}%
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

            <section aria-label="Signals">
              <SectionHead
                title="Signals"
                detail={recentSignals.length ? `Last ${recentSignals.length}` : undefined}
                count={recentSignals.length || undefined}
              />
              {recentSignals.length === 0 ? (
                <QuietEmpty>No high-priority events detected in the last cycle.</QuietEmpty>
              ) : (
                <ul className="mt-phi-2 flex flex-col">
                  {recentSignals.map((sig, i) => {
                    const companyName = sig.startup_id ? startupNameById.get(sig.startup_id) : null;
                    const body = (
                      <>
                        <span className="flex items-baseline justify-between gap-phi-3">
                          <span className="type-label-section min-w-0 truncate">
                            {companyName ?? sig.signal_type.replace(/_/g, ' ')}
                          </span>
                          <span className="type-data shrink-0 text-oxford/60">
                            {signalWhen(sig)}
                          </span>
                        </span>
                        {sig.description ? (
                          <span className="mt-phi-1 block type-body-sm leading-relaxed text-oxford/65">
                            {sig.description}
                          </span>
                        ) : null}
                      </>
                    );
                    return (
                      <li key={sig.id ?? i} className="border-b border-oxford/[0.06]">
                        {sig.startup_id && startupNameById.has(sig.startup_id) ? (
                          <button
                            type="button"
                            onClick={() => openDeal(sig.startup_id!)}
                            className="group block w-full py-phi-3 text-left transition-colors hover:bg-oxford/[0.05] btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
                          >
                            {body}
                          </button>
                        ) : (
                          <div className="py-phi-3">{body}</div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
