import { useMemo } from 'react';
import { useNavigate } from 'react-router';
import type { SystemData } from '../hooks/useSystemData';
import type { Startup, SignalItem } from '../types/startup';
import { isDealHumanResolved } from '../lib/dealState';
import { buildTrackRecord } from '../lib/trackRecord';

function recOf(s: Startup): string | null {
  const r = s.partner?.recommendation;
  return typeof r === 'string' && r ? r.toUpperCase() : null;
}

/** Instrument readout — a number with its label, no box. */
function Readout({ label, value, tone }: { label: string; value: string; tone?: 'escalation' }) {
  return (
    <div className="flex flex-col gap-phi-1">
      <span
        className={`font-mono text-[clamp(22px,2vw,30px)] font-semibold leading-none tracking-[-0.03em] tabular-nums ${
          tone === 'escalation' ? 'text-escalation' : 'text-oxford'
        }`}
      >
        {value}
      </span>
      <span className="type-meta uppercase tracking-[0.1em] text-oxford/40">{label}</span>
    </div>
  );
}

function SectionHead({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-phi-4 border-t border-oxford/[0.075] pt-phi-4">
      <h2 className="type-label-section text-oxford/72">{title}</h2>
      {detail ? <span className="type-meta tabular-nums text-oxford/35">{detail}</span> : null}
    </div>
  );
}

function QuietEmpty({ children }: { children: React.ReactNode }) {
  return <p className="mt-phi-4 type-body-sm text-oxford/45">{children}</p>;
}

function signalWhen(sig: SignalItem): string {
  if (!sig.detected_at) return '—';
  const d = new Date(sig.detected_at);
  return `${d.toLocaleDateString('en-GB')} ${d.toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit' })}`;
}

/**
 * Portfolio — conviction monitoring. The book the system has built, the
 * watchlist holding pressure, and the signals moving against both. Built
 * entirely from data the pipeline already persists; no fabricated returns.
 */
export default function PortfolioPage({ data }: { data: SystemData }) {
  const navigate = useNavigate();
  const openDeal = (id: string) => navigate(`/v1?open=${id}`);

  const track = useMemo(
    () => buildTrackRecord(data.startups, data.calibrationState, data.systemHealth?.calibration_warning ?? null),
    [data.startups, data.calibrationState, data.systemHealth],
  );

  const startupNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const s of data.startups) {
      if (s.scout?.name) map.set(s.id, s.scout.name);
    }
    return map;
  }, [data.startups]);

  const convictionBook = useMemo(
    () =>
      data.startups
        .filter((s) => recOf(s) === 'INVEST')
        .sort((a, b) => (b.timestamps?.partnered_at ?? '').localeCompare(a.timestamps?.partnered_at ?? '')),
    [data.startups],
  );

  const sectorRows = useMemo(() => {
    const entries = Object.entries(data.concentrationAnalytics.by_sector ?? {});
    return entries
      .map(([sector, v]) => ({ sector, count: v.count, pct: v.pct_of_total }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [data.concentrationAnalytics]);
  const maxSectorCount = Math.max(...sectorRows.map((r) => r.count), 1);

  const watchlistEntries = data.watchlistAnalytics.entries ?? [];
  const recentSignals = (data.signals ?? []).slice(0, 12);

  return (
    <div className="page-transition-enter min-h-0 flex-1 overflow-y-auto overscroll-contain">
      <div className="mx-auto w-full max-w-[1180px] px-phi-5 pb-phi-8 pt-phi-5">
        {/* ── Header: place + book composition in one line of sight ── */}
        <header className="flex flex-wrap items-end justify-between gap-x-phi-7 gap-y-phi-5 pb-phi-6">
          <div className="min-w-0">
            <p className="type-label-section text-oxford/45">Conviction</p>
            <h1 className="mt-phi-2 type-title font-medium text-oxford">Portfolio</h1>
          </div>
          <div className="flex flex-wrap items-end gap-x-phi-7 gap-y-phi-4">
            <Readout label="Conviction" value={track.investCount.toLocaleString()} />
            <Readout label="Monitor" value={track.monitorCount.toLocaleString()} />
            <Readout label="Watchlist" value={data.watchlistAnalytics.total.toLocaleString()} />
            <Readout label="Ruled" value={track.humanRuledCount.toLocaleString()} />
            <Readout
              label="Need ruling"
              value={(data.pendingEscalationCount ?? 0).toLocaleString()}
              tone={data.pendingEscalationCount > 0 ? 'escalation' : undefined}
            />
          </div>
        </header>

        <div className="grid grid-cols-1 gap-x-phi-7 gap-y-phi-6 lg:grid-cols-[minmax(0,61.8fr)_minmax(0,38.2fr)]">
          {/* ── Conviction book ── */}
          <div className="flex min-w-0 flex-col gap-phi-6">
            <section aria-label="Conviction book">
              <SectionHead title="Conviction book" detail={convictionBook.length.toLocaleString()} />
              {convictionBook.length === 0 ? (
                <QuietEmpty>No conviction positions yet. INVEST decisions land here as the pipeline rules.</QuietEmpty>
              ) : (
                <ul className="mt-phi-2 flex flex-col">
                  {convictionBook.map((s) => (
                    <li key={s.id}>
                      <button
                        type="button"
                        onClick={() => openDeal(s.id)}
                        className="flex w-full items-center justify-between gap-phi-4 border-b border-oxford/[0.06] py-phi-3 text-left transition-colors hover:bg-registerTint btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
                      >
                        <span className="min-w-0">
                          <span className="block truncate type-body-emphasis text-oxford">{s.scout.name}</span>
                          <span className="block truncate type-meta text-oxford/45">
                            {[s.scout.sector, s.scout.funding_stage].filter(Boolean).join(' · ') || '—'}
                          </span>
                        </span>
                        <span className="flex shrink-0 items-center gap-phi-4">
                          {isDealHumanResolved(s) ? (
                            <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-oxford/40">Ruled</span>
                          ) : null}
                          {s.review?.overall_score != null ? (
                            <span className="font-mono text-[13px] tabular-nums text-oxford/70">
                              {Number(s.review.overall_score).toFixed(1)}
                            </span>
                          ) : null}
                        </span>
                      </button>
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
                <QuietEmpty>Distribution appears once the pipeline has decided deals to cluster.</QuietEmpty>
              ) : (
                <ul className="mt-phi-4 flex flex-col gap-phi-3">
                  {sectorRows.map((row) => (
                    <li key={row.sector} className="grid grid-cols-[minmax(90px,140px)_1fr_64px] items-center gap-phi-4">
                      <span className="truncate type-meta uppercase tracking-[0.1em] text-oxford/55">{row.sector}</span>
                      <span className="relative block h-px bg-oxford/10">
                        <span
                          className="absolute inset-y-0 left-0 bg-oxford/45"
                          style={{ width: `${Math.max(2, Math.min(100, (row.count / maxSectorCount) * 100))}%` }}
                        />
                      </span>
                      <span className="text-right font-mono text-[11px] tabular-nums text-oxford/50">
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
              />
              {watchlistEntries.length === 0 ? (
                <QuietEmpty>Nothing held under observation.</QuietEmpty>
              ) : (
                <ul className="mt-phi-2 flex flex-col">
                  {watchlistEntries.slice(0, 12).map((e, i) => (
                    <li key={e.startup_id ?? i}>
                      <button
                        type="button"
                        onClick={() => e.startup_id && openDeal(e.startup_id)}
                        disabled={!e.startup_id}
                        className="flex w-full items-center justify-between gap-phi-3 border-b border-oxford/[0.06] py-phi-2 text-left transition-colors hover:bg-registerTint disabled:cursor-default btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
                      >
                        <span className="min-w-0 truncate type-body-sm text-oxford">
                          {e.startup_name ?? (e.startup_id ? startupNameById.get(e.startup_id) : null) ?? 'Unknown'}
                        </span>
                        <span
                          className={`shrink-0 font-mono text-[11px] tabular-nums ${
                            e.stale_warning ? 'text-escalation' : 'text-oxford/45'
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
              <SectionHead title="Signals" detail={recentSignals.length ? `Last ${recentSignals.length}` : undefined} />
              {recentSignals.length === 0 ? (
                <QuietEmpty>No high-priority events detected in the last cycle.</QuietEmpty>
              ) : (
                <ul className="mt-phi-2 flex flex-col">
                  {recentSignals.map((sig, i) => {
                    const companyName = sig.startup_id ? startupNameById.get(sig.startup_id) : null;
                    const body = (
                      <>
                        <span className="flex items-baseline justify-between gap-phi-3">
                          <span className="min-w-0 truncate type-meta uppercase tracking-[0.08em] text-oxford/55">
                            {companyName ?? sig.signal_type.replace(/_/g, ' ')}
                          </span>
                          <span className="shrink-0 font-mono text-[10px] tabular-nums tracking-[0.04em] text-oxford/35">
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
                            className="block w-full py-phi-3 text-left transition-colors hover:bg-registerTint btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
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
