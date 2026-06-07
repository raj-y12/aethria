import { useMemo } from 'react';
import { useNavigate } from 'react-router';
import PageChrome from '../components/PageChrome';
import type { SystemData } from '../hooks/useSystemData';
import type { Startup } from '../types/startup';
import { isDealHumanResolved } from '../lib/dealState';
import { buildTrackRecord } from '../lib/trackRecord';

function recOf(s: Startup): string | null {
  const r = s.partner?.recommendation;
  return typeof r === 'string' && r ? r.toUpperCase() : null;
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: 'escalation' }) {
  return (
    <div className="flex flex-col gap-phi-1 border border-oxford/[0.08] px-phi-4 py-phi-3">
      <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-oxford/40">{label}</p>
      <p className={`font-mono text-[1.6rem] font-semibold leading-none tabular-nums ${tone === 'escalation' ? 'text-escalation' : 'text-oxford'}`}>
        {value}
      </p>
    </div>
  );
}

function SectionHead({ children }: { children: React.ReactNode }) {
  return <h2 className="mb-phi-3 type-label-section text-oxford/72">{children}</h2>;
}

/**
 * Portfolio — the fund-level view: book composition, sector concentration, the
 * INVEST book, and the watchlist. Built entirely from data the pipeline already
 * persists; no fabricated returns or marks.
 */
export default function PortfolioPage({ data }: { data: SystemData }) {
  const navigate = useNavigate();
  const openDeal = (id: string) => navigate(`/v1/deal/${id}`);

  const track = useMemo(
    () => buildTrackRecord(data.startups, data.calibrationState, data.systemHealth?.calibration_warning ?? null),
    [data.startups, data.calibrationState, data.systemHealth],
  );

  const investBook = useMemo(
    () =>
      data.startups
        .filter((s) => recOf(s) === 'INVEST')
        .sort((a, b) =>
          (b.timestamps?.partnered_at ?? '').localeCompare(a.timestamps?.partnered_at ?? ''),
        ),
    [data.startups],
  );

  const sectorRows = useMemo(() => {
    const entries = Object.entries(data.concentrationAnalytics.by_sector ?? {});
    return entries
      .map(([sector, v]) => ({ sector, count: v.count, pct: v.pct_of_total }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [data.concentrationAnalytics]);

  const watchlistEntries = data.watchlistAnalytics.entries ?? [];
  const recentSignals = (data.signals ?? []).slice(0, 8);

  return (
    <PageChrome title="Portfolio" kicker="Fund book">
      {/* ── Book composition ── */}
      <div className="grid grid-cols-2 gap-phi-3 sm:grid-cols-3 lg:grid-cols-5">
        <Stat label="Invest" value={track.investCount.toLocaleString()} />
        <Stat label="Monitor" value={track.monitorCount.toLocaleString()} />
        <Stat label="Pass" value={track.passCount.toLocaleString()} />
        <Stat label="Human ruled" value={track.humanRuledCount.toLocaleString()} />
        <Stat
          label="Need ruling"
          value={(data.pendingEscalationCount ?? 0).toLocaleString()}
          tone={data.pendingEscalationCount > 0 ? 'escalation' : undefined}
        />
      </div>

      <div className="mt-phi-6 grid grid-cols-1 gap-phi-6 lg:grid-cols-2">
        {/* ── Sector concentration ── */}
        <section>
          <SectionHead>Sector concentration</SectionHead>
          {sectorRows.length === 0 ? (
            <p className="type-meta text-oxford/40">No decided deals yet.</p>
          ) : (
            <ul className="flex flex-col gap-phi-2">
              {sectorRows.map((row) => (
                <li key={row.sector} className="flex items-center gap-phi-3">
                  <span className="w-32 shrink-0 truncate type-body-sm text-oxford/80">{row.sector}</span>
                  <span className="relative h-2 flex-1 bg-oxford/[0.06]">
                    <span
                      className="absolute inset-y-0 left-0 bg-oxford/55"
                      style={{ width: `${Math.max(3, Math.min(100, row.pct))}%` }}
                    />
                  </span>
                  <span className="w-16 shrink-0 text-right font-mono text-[11px] tabular-nums text-oxford/55">
                    {row.count} · {row.pct.toFixed(0)}%
                  </span>
                </li>
              ))}
            </ul>
          )}
          {data.concentrationAnalytics.most_concentrated_sector ? (
            <p className="mt-phi-3 type-meta text-oxford/40">
              Most concentrated: {data.concentrationAnalytics.most_concentrated_sector}
            </p>
          ) : null}
        </section>

        {/* ── Watchlist ── */}
        <section>
          <SectionHead>
            Watchlist · {data.watchlistAnalytics.total} ({data.watchlistAnalytics.stale} stale)
          </SectionHead>
          {watchlistEntries.length === 0 ? (
            <p className="type-meta text-oxford/40">Nothing on the watchlist.</p>
          ) : (
            <ul className="flex flex-col">
              {watchlistEntries.slice(0, 10).map((e, i) => (
                <li key={e.startup_id ?? i}>
                  <button
                    type="button"
                    onClick={() => e.startup_id && openDeal(e.startup_id)}
                    disabled={!e.startup_id}
                    className="flex w-full items-center justify-between gap-phi-3 border-b border-oxford/[0.06] py-phi-2 text-left transition-colors hover:bg-oxford/[0.025] disabled:cursor-default btn-interaction"
                  >
                    <span className="min-w-0 truncate type-body-sm text-oxford">
                      {e.startup_name ?? e.startup_id ?? 'Unknown'}
                    </span>
                    <span className={`shrink-0 font-mono text-[11px] tabular-nums ${e.stale_warning ? 'text-escalation' : 'text-oxford/45'}`}>
                      {e.days_on_watchlist != null ? `${e.days_on_watchlist}d` : '—'}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {/* ── The invest book ── */}
      <section className="mt-phi-6">
        <SectionHead>Invest book · {investBook.length}</SectionHead>
        {investBook.length === 0 ? (
          <p className="type-meta text-oxford/40">No INVEST recommendations yet.</p>
        ) : (
          <ul className="flex flex-col">
            {investBook.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => openDeal(s.id)}
                  className="flex w-full items-center justify-between gap-phi-4 border-b border-oxford/[0.06] py-phi-3 text-left transition-colors hover:bg-oxford/[0.025] btn-interaction"
                >
                  <span className="min-w-0">
                    <span className="block truncate type-body-emphasis text-oxford">{s.scout.name}</span>
                    <span className="block truncate type-meta text-oxford/45">
                      {[s.scout.sector, s.scout.funding_stage].filter(Boolean).join(' · ') || '—'}
                    </span>
                  </span>
                  <span className="flex shrink-0 items-center gap-phi-3">
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

      {/* ── Recent signals ── */}
      {recentSignals.length > 0 ? (
        <section className="mt-phi-6">
          <SectionHead>Recent signals</SectionHead>
          <ul className="flex flex-col gap-phi-2">
            {recentSignals.map((sig, i) => (
              <li key={sig.id ?? i} className="flex items-baseline gap-phi-3">
                <span className="shrink-0 font-mono text-[10px] uppercase tracking-[0.12em] text-oxford/40">
                  {sig.signal_type}
                </span>
                <span className="min-w-0 type-body-sm text-oxford/70">{sig.description ?? '—'}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </PageChrome>
  );
}
