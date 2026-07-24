import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { motion } from 'framer-motion';
import RoomHeader from '../components/RoomHeader';
import Reveal from '../components/Reveal';
import { workspaceLayout } from '../design-system/workspaceLayout';
import { usePrefersReducedMotion, useCountUp } from '../hooks';
import type { SystemData } from '../hooks/useSystemData';
import type { Startup, SignalItem } from '../types/startup';
import { formatDateTime } from '../lib/dates';

function recOf(s: Startup): string | null {
  const r = s.partner?.recommendation;
  return typeof r === 'string' && r ? r.toUpperCase() : null;
}

type LedgerState = 'invested' | 'monitoring' | 'passed';

/* The book holds only *decided* deals, grouped by the ruling you actually made.
 * Deals still awaiting a ruling are work, not record — they live in Flow, and
 * the portfolio only points to them (see the pointer below the tabs). */
const LEDGER_SEGMENTS: { key: LedgerState; label: string; empty: string }[] = [
  { key: 'invested', label: 'Invested', empty: 'No positions yet. A company becomes a position when you rule it INVEST — a recommendation alone does not.' },
  { key: 'monitoring', label: 'Monitoring', empty: 'Nothing under monitoring. Deals you rule MONITOR land here.' },
  { key: 'passed', label: 'Passed', empty: 'Nothing passed yet. Declined deals stay here, searchable.' },
];

/** Compact ruling date, or an em dash. */
function ruledWhen(s: Startup): string {
  const iso = s.human_resolution?.resolved_at;
  if (!iso) return '—';
  const t = new Date(iso);
  return Number.isNaN(t.getTime()) ? '—' : t.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/** Instrument readout — bordered Record-plate dims cell. Counts up on arrival
 * (mirrors Fund's HeaderReadout dims-grid construction). */
function Readout({ label, value, tone }: { label: string; value: number; tone?: 'escalation' }) {
  const shown = useCountUp(value);
  return (
    <div className="flex flex-col gap-phi-1 bg-paper px-phi-4 py-phi-3">
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
 * Portfolio — the *record*: the book of decided deals grouped by ruling
 * (invested, monitoring, passed), with concentration, watchlist, and signals.
 * Deals awaiting a ruling are *work*, not record — they stay in Flow; the book
 * only points to them. Built from data the pipeline already persists; no
 * fabricated returns.
 */
export default function PortfolioPage({ data }: { data: SystemData }) {
  const navigate = useNavigate();
  const reduceMotion = usePrefersReducedMotion();
  const [activeState, setActiveState] = useState<LedgerState>('invested');
  const openDeal = (id: string) => navigate(`/v1/flow?open=${id}`);

  const { buckets, awaitingCount } = useMemo(() => {
    const buckets: Record<LedgerState, Startup[]> = { invested: [], monitoring: [], passed: [] };
    let awaitingCount = 0;
    for (const s of data.startups) {
      const decision = s.human_resolution?.decision;
      if (decision === 'YES') buckets.invested.push(s);
      else if (decision === 'MAYBE') buckets.monitoring.push(s);
      else if (decision === 'NO') buckets.passed.push(s);
      else if (recOf(s)) awaitingCount += 1;
    }
    const recency = (s: Startup) =>
      s.human_resolution?.resolved_at ?? s.timestamps?.partnered_at ?? s.timestamps?.reviewed_at ?? '';
    (Object.keys(buckets) as LedgerState[]).forEach((key) => {
      buckets[key].sort((a, b) => recency(b).localeCompare(recency(a)));
    });
    return { buckets, awaitingCount };
  }, [data.startups]);

  const activeRows = buckets[activeState];

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
    <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
      <div className={`${workspaceLayout.shell} ${workspaceLayout.pageTop} ${workspaceLayout.pageBottom}`}>
        {/* ── Header: place + book composition in one line of sight ── */}
        <RoomHeader
          className={workspaceLayout.headerBottom}
          eyebrow="Conviction"
          title="Portfolio"
          plateIndex="03 — 04"
          readouts={
            // Record-plate dims cells — 1px section-divider grid lines via the
            // gap+background trick (marketing `.dims` pattern), mirrors Fund's
            // HeaderReadout construction (Task 3).
            <div className="grid grid-cols-3 gap-px border border-[var(--section-divider)] bg-[var(--section-divider)]">
              <Readout label="Invested" value={buckets.invested.length} />
              <Readout label="Monitoring" value={buckets.monitoring.length} />
              <Readout label="Passed" value={buckets.passed.length} />
            </div>
          }
        />

        <Reveal delay={0.22} y={12}>
        <div className="grid grid-cols-1 gap-x-phi-7 gap-y-phi-6 lg:grid-cols-[minmax(0,61.8fr)_minmax(0,38.2fr)]">
          {/* ── Decision ledger (the record) ── */}
          <div className="flex min-w-0 flex-col gap-phi-6">
            <section aria-label="Decision ledger">
              <SectionHead title="The book" detail={`${activeRows.length} shown`} count={activeRows.length} />
              <div aria-label="Deal state" className="mt-phi-3 flex flex-wrap gap-phi-2">
                {LEDGER_SEGMENTS.map((seg) => {
                  const active = seg.key === activeState;
                  return (
                    <button
                      key={seg.key}
                      type="button"
                      aria-pressed={active}
                      onClick={() => setActiveState(seg.key)}
                      className={`type-status flex items-center gap-phi-2 px-phi-3 py-phi-1 transition-colors btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 ${
                        active
                          ? 'bg-oxford/[0.05] text-oxford'
                          : 'text-oxford/55 hover:bg-oxford/[0.03] hover:text-oxford'
                      }`}
                    >
                      <span>{seg.label}</span>
                      <span className="type-data tabular-nums text-oxford/45">{buckets[seg.key].length}</span>
                    </button>
                  );
                })}
              </div>

              {/* Pointer, not a worklist — ruling happens in Flow, the book only points there. */}
              {awaitingCount > 0 ? (
                <button
                  type="button"
                  onClick={() => navigate('/v1/flow')}
                  className="group mt-phi-3 inline-flex items-center gap-phi-2 type-body-sm text-oxford/60 transition-colors hover:text-oxford focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
                >
                  <span className="type-data tabular-nums text-oxford">{awaitingCount}</span>
                  <span>awaiting your ruling — rule in Flow</span>
                  <span aria-hidden className="transition-transform duration-200 group-hover:translate-x-[2px]">→</span>
                </button>
              ) : null}

              <motion.div
                key={activeState}
                initial={reduceMotion ? false : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
              >
              {activeRows.length === 0 ? (
                <QuietEmpty>{LEDGER_SEGMENTS.find((s) => s.key === activeState)?.empty}</QuietEmpty>
              ) : (
                <>
                  <div
                    className={`mt-phi-4 hidden border-b border-oxford/[0.06] pb-phi-2 ${LEDGER_GRID}`}
                    aria-hidden
                  >
                    <span className="type-label-section">Company</span>
                    <span className="type-label-section">Sector</span>
                    <span className="type-label-section">Stage</span>
                    <span className="type-label-section text-right">Score</span>
                    <span className="type-label-section text-right">Ruled</span>
                  </div>
                  <ul className="flex flex-col lg:mt-0 mt-phi-3">
                    {activeRows.map((s) => (
                      <li key={s.id} className="border-b border-oxford/[0.06]">
                        <button
                          type="button"
                          onClick={() => openDeal(s.id)}
                          className={`group -mx-phi-3 flex w-[calc(100%+2*var(--space-3))] items-center gap-phi-4 px-phi-3 py-phi-3 text-left transition-colors hover:bg-oxford/[0.05] btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 ${LEDGER_GRID}`}
                        >
                          <span className="min-w-0 flex-1 transition-transform duration-200 group-hover:translate-x-[2px]">
                            <span className="block truncate type-body-emphasis text-oxford">{s.scout.name}</span>
                            <span className="block truncate type-meta text-oxford/60 lg:hidden">
                              {[s.scout.sector, s.scout.funding_stage, ruledWhen(s)]
                                .filter(Boolean)
                                .join(' · ') || '—'}
                            </span>
                          </span>
                          <span className="hidden min-w-0 truncate type-meta text-oxford/60 lg:block">
                            {s.scout.sector || '—'}
                          </span>
                          <span className="hidden min-w-0 truncate type-meta text-oxford/60 lg:block">
                            {s.scout.funding_stage || '—'}
                          </span>
                          <span className="type-data shrink-0 text-right text-oxford/70 transition-colors group-hover:text-oxford">
                            {s.review?.overall_score != null ? Number(s.review.overall_score).toFixed(1) : '—'}
                          </span>
                          <span className="type-meta hidden shrink-0 truncate text-right text-oxford/60 lg:block">
                            {ruledWhen(s)}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </>
              )}
              </motion.div>
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
        </Reveal>
      </div>
    </div>
  );
}
