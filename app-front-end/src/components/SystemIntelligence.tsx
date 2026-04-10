import { useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { tokens } from '../design-system/tokens';
import {
  PANEL_TAB_BAR_CLASS,
  PANEL_TAB_ACTIVE_CLASS,
  PANEL_TAB_INACTIVE_CLASS,
} from './PanelShell';
import SignalEventRow from './SignalEventRow';
import type {
  SignalItem, EscalationItem, RejectionAnalytics, WatchlistAnalytics,
  ConcentrationAnalytics, MetaCycleReport, ScoutWeights, CalibrationState,
} from '../types/startup';
import { resolveEscalation } from '../api/escalations';
import { triggerMetaCycle } from '../api/meta';
import { transitionOrReduced } from '../design-system/motion';
import { usePrefersReducedMotion } from '../hooks';
import EmptyState from './EmptyState';
import DecisionBadge from './DecisionBadge';
import { fetchFundThesisRuntime, type FundThesisRuntime } from '../api/fundThesis';

/** Match pipeline tab strip: bottom border on the nav hairline (items-end + -mb-px, same language as `PanelShell`). */
const SYSTEM_INTEL_TAB_BUTTON_CLASS =
  'py-2.5 px-3 type-label-tab border-b border-transparent -mb-px focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-inset btn-interaction transition-[border-color,color]';
const SYSTEM_INTEL_TAB_BAR_CLASS = `${PANEL_TAB_BAR_CLASS} items-end pt-2 pb-0`;

type Tab = 'signals' | 'escalations' | 'analytics' | 'thesis' | 'meta';
const TABS: { key: Tab; label: string }[] = [
  { key: 'escalations', label: 'Escalations' },
  { key: 'signals', label: 'Signals' },
  { key: 'analytics', label: 'Analytics' },
  { key: 'thesis', label: 'Fund thesis' },
  { key: 'meta', label: 'Meta-Agent' },
];

interface SystemIntelligenceProps {
  signals: SignalItem[];
  escalations: EscalationItem[];
  rejectionAnalytics: RejectionAnalytics;
  watchlistAnalytics: WatchlistAnalytics;
  concentrationAnalytics: ConcentrationAnalytics;
  metaReports: MetaCycleReport[];
  scoutWeights: ScoutWeights;
  calibrationState: CalibrationState;
  onEscalationResolved?: () => void;
  /** Open the work-grid memo for this escalation’s startup (closes System, selects startup). */
  onOpenEscalationMemo?: (escalation: EscalationItem) => void;
}

function formatRelativeTime(isoDate: string): string {
  const diff = new Date(isoDate).getTime() - Date.now();
  if (diff <= 0) return 'overdue';
  const hours = Math.floor(diff / 3600000);
  const mins = Math.floor((diff % 3600000) / 60000);
  if (hours > 0) return `in ${hours}h ${mins}m`;
  return `in ${mins}m`;
}

function BarFill({ pct, delay = 0 }: { pct: number; delay?: number }) {
  const reduceMotion = usePrefersReducedMotion();
  return (
    <div className="w-full h-1.5 bg-oxford/25">
      <motion.div
        className="h-full bg-oxford/50"
        initial={reduceMotion ? { width: `${Math.min(100, Math.max(0, pct))}%` } : { width: 0 }}
        animate={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
        transition={transitionOrReduced(reduceMotion, {
          duration: tokens.motion.duration.short,
          delay: reduceMotion ? 0 : delay,
          ease: tokens.motion.ease,
        })}
      />
    </div>
  );
}

/* ─── SIGNALS ─── */
function SignalsTab({ signals }: { signals: SignalItem[] }) {
  if (signals.length === 0) {
    return (
      <EmptyState
        label="Signals"
        body="News, funding, and other updates for companies in your pipeline appear here as they are detected."
      />
    );
  }
  return (
    <div className="space-y-0">
      {signals.map((sig, i) => (
        <SignalEventRow
          key={sig.id ?? i}
          layout="stacked"
          timestamp={
            sig.detected_at
              ? new Date(sig.detected_at).toLocaleTimeString('en-GB', {
                  hour12: false,
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                })
              : '—'
          }
          label={`${sig.startup_id?.slice(0, 8) ?? 'Unknown'} · ${sig.signal_type.replace('_', ' ')}`}
          body={<span className="line-clamp-2">{sig.description}</span>}
          meta={`${sig.tracker_agent_id ?? sig.source ?? ''} · ${sig.detected_at ? new Date(sig.detected_at).toLocaleDateString('en-GB') : ''}`}
        />
      ))}
    </div>
  );
}

/* ─── ESCALATIONS ─── */
function EscalationsTab({
  escalations,
  onResolved,
  onOpenMemo,
}: {
  escalations: EscalationItem[];
  onResolved?: () => void;
  onOpenMemo?: (escalation: EscalationItem) => void;
}) {
  const pending = escalations.filter((e) => !e.human_resolution);
  if (pending.length === 0) {
    return <p className="text-center py-12 type-label-section text-oxford/25">No pending escalations</p>;
  }
  return (
    <div className="space-y-0">
      {pending.map((esc) => (
        <EscalationCard key={esc.id} escalation={esc} onResolved={onResolved} onOpenMemo={onOpenMemo} />
      ))}
    </div>
  );
}

function escalationConvictionScore(partner: EscalationItem['partner']): number | null {
  const c = partner?.confidence;
  if (c == null || typeof c !== 'number' || Number.isNaN(c)) return null;
  return c;
}

function EscalationCard({
  escalation,
  onResolved,
  onOpenMemo,
}: {
  escalation: EscalationItem;
  onResolved?: () => void;
  onOpenMemo?: (escalation: EscalationItem) => void;
}) {
  const reduceMotion = usePrefersReducedMotion();
  const [resolving, setResolving] = useState<string | null>(null);
  const [notes, setNotes] = useState('');
  const [resolved, setResolved] = useState(false);

  const handleResolve = useCallback(async () => {
    if (!resolving) return;
    try {
      await resolveEscalation(escalation.id, resolving as 'YES' | 'NO' | 'MAYBE', notes);
      setResolved(true);
      setTimeout(() => onResolved?.(), 1500);
    } catch { /* silent */ }
  }, [resolving, notes, escalation.id, onResolved]);

  const conviction = escalationConvictionScore(escalation.partner);
  const sector = escalation.scout?.sector?.trim() ?? '';
  const sectorConvictionLine =
    sector || conviction != null
      ? [
          sector || null,
          conviction != null ? `Conviction ${conviction}/10` : null,
        ]
          .filter(Boolean)
          .join(' · ')
      : null;

  if (resolved) {
    return (
      <motion.div
        initial={{ opacity: 1, height: 'auto' }}
        animate={{ opacity: 0, height: 0 }}
        transition={transitionOrReduced(reduceMotion, {
          duration: tokens.motion.duration.short,
          ease: tokens.motion.ease,
        })}
        className="overflow-hidden"
      >
        <p className="py-4 text-center type-label-tab text-oxford/60">Resolved</p>
      </motion.div>
    );
  }

  return (
    <div className="border-b border-oxford/[0.08] py-3 shadow-none">
      <div className="flex items-start justify-between gap-3 w-full min-w-0">
        <p
          className="min-w-0 flex-1 truncate text-[15px] font-medium leading-[1.5] text-oxford/90"
          style={{ fontFamily: '"Geist Sans", system-ui, sans-serif' }}
        >
          {escalation.startup_name ?? escalation.scout?.name ?? escalation.id}
        </p>
        {onOpenMemo ? (
          <button
            type="button"
            onClick={() => onOpenMemo(escalation)}
            className="shrink-0 inline-flex min-h-7 items-center cursor-pointer rounded-none border border-solid border-oxford/15 bg-transparent px-2.5 py-1 font-mono text-[10px] font-normal uppercase leading-none tracking-[0.1em] text-oxford/65 transition-[background-color,border-color,color,transform] duration-150 ease-out hover:bg-oxford/[0.04] hover:border-oxford/35 hover:text-oxford active:translate-y-px btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-offset-0"
          >
            → MEMO
          </button>
        ) : null}
      </div>
      <p
        className="mt-1 inline-flex w-fit min-h-6 items-center rounded-none border border-solid border-oxford/10 bg-transparent px-2 py-0.5 text-[10px] font-normal uppercase leading-[1.5] tracking-[0.08em] text-oxford/50"
        style={{ fontFamily: '"Space Mono", ui-monospace, monospace' }}
      >
        Awaiting human review
      </p>
      {sectorConvictionLine ? (
        <p className="mt-2 font-body text-[13px] leading-[1.6] text-oxford/60">{sectorConvictionLine}</p>
      ) : null}
      {escalation.partner?.rationale && (
        <p className="type-body-sm text-oxford/80 mt-2 leading-[1.6] line-clamp-3">{escalation.partner.rationale}</p>
      )}
      {escalation.partner?.llm_fallback_reason && (
        <p className="type-body-sm italic text-oxford/60 mt-1">{escalation.partner.llm_fallback_reason}</p>
      )}
      {!resolving ? (
        <div className="mt-3 flex flex-wrap items-center">
          {(
            [
              {
                d: 'YES' as const,
                label: 'ADVANCE',
                toneClass:
                  'border-oxford/30 text-oxford/90 hover:bg-oxford/[0.08] hover:border-oxford/45',
              },
              {
                d: 'NO' as const,
                label: 'PASS',
                toneClass:
                  'border-oxford/18 text-oxford/70 hover:bg-oxford/[0.05] hover:border-oxford/35',
              },
              {
                d: 'MAYBE' as const,
                label: 'HOLD',
                toneClass:
                  'border-oxford/18 text-oxford/70 hover:bg-oxford/[0.05] hover:border-oxford/35',
              },
            ] as const
          ).map(({ d, label, toneClass }, i) => (
            <div key={d} className="flex items-center">
              {i > 0 ? <span className="mx-0.5 h-3 w-px shrink-0 bg-oxford/[0.15]" aria-hidden /> : null}
              <button
                type="button"
                onClick={() => setResolving(d)}
                className={`${toneClass} rounded-none border border-solid bg-transparent py-1 px-3 font-mono text-[10px] font-normal uppercase leading-[1.5] tracking-[0.1em] transition-[background-color,border-color,color,transform] duration-150 btn-interaction active:translate-y-px focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-offset-0`}
              >
                {label}
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-3 space-y-2">
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add a note before deciding..."
            className="min-h-[80px] w-full resize-none rounded-none border border-solid border-field-border bg-paper p-3 text-[14px] font-normal leading-[1.6] text-oxford/70 outline-none transition-[border-color] duration-150 placeholder:text-[14px] placeholder:font-normal placeholder:text-oxford/30 focus:border-field-border-strong focus:outline-none"
            style={{ fontFamily: '"Geist Sans", system-ui, sans-serif' }}
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleResolve}
              disabled={notes.trim().length < 10}
              className={`flex-1 py-2 type-label-tab text-paper btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-inset ${
                notes.trim().length >= 10
                  ? 'cursor-pointer bg-oxford hover:bg-oxford/90'
                  : 'cursor-not-allowed bg-oxford/30'
              }`}
            >
              Confirm {resolving === 'YES' ? 'Advance' : resolving === 'NO' ? 'Pass' : 'Hold'}
            </button>
            <button
              onClick={() => { setResolving(null); setNotes(''); }}
              className="py-2 px-3 type-label-tab text-oxford/60 border border-oxford/25 hover:text-oxford hover:border-oxford/40 hover:bg-oxford/[0.03] btn-interaction"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── ANALYTICS ─── */
function AnalyticsTab({ rejection, watchlist, concentration }: {
  rejection: RejectionAnalytics; watchlist: WatchlistAnalytics; concentration: ConcentrationAnalytics;
}) {
  const maxRedFlag = Math.max(...rejection.most_common_red_flags.map((r) => r.count), 1);
  const sectors = Object.entries(concentration.by_sector).sort((a, b) => b[1].count - a[1].count).slice(0, 8);
  const maxSector = Math.max(...sectors.map(([, v]) => v.count), 1);
  const hasNoData =
    rejection.most_common_red_flags.length === 0 &&
    watchlist.total === 0 &&
    sectors.length === 0;

  if (hasNoData) {
    return (
      <EmptyState
        label="Analytics"
        body="Rejection patterns, watchlist, and sector concentration fill in after reviewers have worked the queue."
      />
    );
  }

  return (
    <div className="space-y-0">
      {/* Rejection Patterns */}
      <section className="pb-6">
        <h3 className="type-label-section text-oxford/60 mb-3">Rejection patterns</h3>
        {rejection.most_common_red_flags.slice(0, 6).map((rf, i) => (
          <div key={rf.flag} className="flex items-center gap-2 mb-1">
            <span className="type-label-section text-oxford/60 w-32 truncate shrink-0">{rf.flag}</span>
            <div className="flex-1"><BarFill pct={(rf.count / maxRedFlag) * 100} delay={i * 0.05} /></div>
            <span className="type-meta text-oxford/40 tabular-nums w-6 text-right">{rf.count}</span>
          </div>
        ))}
        {rejection.most_common_red_flags.length === 0 && (
          <p className="type-label-tab text-oxford/25">No rejection data yet</p>
        )}
      </section>

      <div className="border-t border-oxford/12" />

      {/* Watchlist Health */}
      <section className="py-6">
        <h3 className="type-label-section text-oxford/60 mb-3">Watchlist health</h3>
        {watchlist.total === 0 ? (
          <div className="py-4 flex items-center justify-center">
            <p className="type-label-section text-oxford/25 text-center">
              NO WATCHLIST ENTRIES
            </p>
          </div>
        ) : (
          <div className="flex gap-6">
            {[
              { label: 'Total', value: watchlist.total },
              { label: 'Stale', value: watchlist.stale },
              { label: 'Avg days', value: Math.round(watchlist.avg_days) },
            ].map((s) => (
              <div key={s.label} className="text-center">
                <p className="type-title text-oxford tabular-nums">{s.value}</p>
                <p className="type-label-section text-oxford/60">{s.label}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="border-t border-oxford/12" />

      {/* Sector Concentration */}
      <section className="pt-6">
        <h3 className="type-label-section text-oxford/60 mb-3">Pipeline concentration</h3>
        <p className="type-meta text-oxford/40 mb-3">Share of pipeline by sector (count · % of total)</p>
        {sectors.map(([sector, data], i) => (
          <div key={sector} className="flex items-center gap-2 mb-1">
            <span className="type-label-section text-oxford/60 w-36 truncate shrink-0">
              {sector}
              {sector === concentration.most_concentrated_sector && (
                <span className="type-meta text-oxford/40 ml-1">concentrated</span>
              )}
            </span>
            <div className="flex-1"><BarFill pct={(data.count / maxSector) * 100} delay={i * 0.05} /></div>
            <span className="type-meta text-oxford/40 tabular-nums whitespace-nowrap min-w-[5rem] text-right" title={`${data.count} companies, ${data.pct_of_total}% of pipeline`}>{data.count} · {data.pct_of_total}%</span>
          </div>
        ))}
        {sectors.length === 0 && <p className="type-label-tab text-oxford/25">No pipeline data yet</p>}
        {concentration.last_updated && (
          <p className="type-meta text-oxford/25 mt-3">Updated {new Date(concentration.last_updated).toLocaleString('en-GB')}</p>
        )}
      </section>
    </div>
  );
}

/* ─── META-AGENT ─── */
function MetaAgentTab({ reports, weights, calibration }: {
  reports: MetaCycleReport[]; weights: ScoutWeights; calibration: CalibrationState;
}) {
  const reduceMotion = usePrefersReducedMotion();
  const [legendOpen, setLegendOpen] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [triggerResult, setTriggerResult] = useState<string | null>(null);

  const handleTrigger = useCallback(async () => {
    setTriggering(true);
    try {
      const result = await triggerMetaCycle();
      setTriggerResult(`Cycle ${result.cycle_number} triggered`);
      setTimeout(() => setTriggerResult(null), 3000);
    } catch {
      setTriggerResult('Failed');
      setTimeout(() => setTriggerResult(null), 3000);
    } finally {
      setTriggering(false);
    }
  }, []);

  const latest = reports.length > 0 ? reports[reports.length - 1] : null;
  const weightEntries: [string, number][] = [
    ['Market', weights.MarketDrivenScout],
    ['Builder', weights.BuilderTechnicalScout],
    ['Pain', weights.PainPointScout],
    ['Contrarian', weights.ContrarianScout],
  ];

  return (
    <div className="space-y-0">
      {/* Pipeline legend — collapsible, hidden by default */}
      <section className="flex-none border-b border-hairline pb-3 mb-3">
        <button
          type="button"
          onClick={() => setLegendOpen((o) => !o)}
          className="w-full flex items-center justify-between py-2 px-0 type-label-tab text-oxford/50 hover:text-oxford/75 btn-interaction text-left"
          aria-expanded={legendOpen}
        >
          <span>Pipeline legend</span>
          <span className="tabular-nums" aria-hidden>{legendOpen ? '−' : '+'}</span>
        </button>
        <AnimatePresence initial={false}>
          {legendOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={transitionOrReduced(reduceMotion, {
                duration: tokens.motion.duration.micro,
                ease: tokens.motion.ease,
              })}
              className="overflow-hidden"
            >
              <div className="pb-2 pt-0 space-y-2 type-body-sm text-oxford/60 max-w-2xl">
                <p><span className="type-label-section text-oxford/60">Order</span> · Escalations first, then recency and score.</p>
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="type-label-section text-oxford/60">Decisions</span>
                  <span className="text-oxford/25" aria-hidden>·</span>
                  <DecisionBadge variant="YES" />
                  <DecisionBadge variant="MAYBE" />
                  <DecisionBadge variant="NO" />
                  <span className="ml-1 type-body-sm text-oxford/60">You decide; scouts and reviewer run automatically.</span>
                </div>
                <p><span className="type-label-section text-oxford/60">Escalation</span> · Reviewer disagreement or low confidence → human resolution. Count in status strip.</p>
                <p><span className="type-label-section text-oxford/60">Pipeline</span> · Scouts surface companies, reviewer scores, partner decides advances and escalations.</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </section>

      {/* Scout Weights */}
      <section className="pb-6">
        <h3 className="type-label-section text-oxford/60 mb-3">Scout allocation</h3>
        {weightEntries.map(([name, w], i) => (
          <div key={name} className="flex items-center gap-2 mb-1.5">
            <span className="type-label-section text-oxford/60 w-20 shrink-0">{name}</span>
            <div className="flex-1"><BarFill pct={w * 100} delay={i * 0.05} /></div>
            <span className="type-meta text-oxford/60 tabular-nums w-8 text-right">{Math.round(w * 100)}%</span>
          </div>
        ))}
      </section>

      <div className="border-t border-oxford/12" />

      {/* Calibration State */}
      <section className="py-6">
        <h3 className="type-label-section text-oxford/60 mb-3">Calibration state</h3>
        {calibration.confidence_threshold_override == null && calibration.reviewer_weak_threshold_override == null ? (
          <p className="type-label-tab text-oxford/40">Running at defaults</p>
        ) : (
          <div className="space-y-1">
            {calibration.confidence_threshold_override != null && (
              <p className="type-body-sm text-oxford/60">
                Confidence threshold: {calibration.confidence_threshold_override}
              </p>
            )}
            {calibration.reviewer_weak_threshold_override != null && (
              <p className="type-body-sm text-oxford/60">
                Weak threshold: {calibration.reviewer_weak_threshold_override}
              </p>
            )}
          </div>
        )}
        {calibration.last_calibrated_at && (
          <p className="type-meta text-oxford/25 mt-2">
            Last calibrated: {new Date(calibration.last_calibrated_at).toLocaleString('en-GB')}
          </p>
        )}
        {calibration.calibration_history.length > 0 && (
          <div className="mt-3 space-y-1">
            {calibration.calibration_history.slice(-5).reverse().map((h, i) => (
              <p key={i} className="type-body-sm text-oxford/40">
                {h.direction === 'tightened' ? '↑' : h.direction === 'loosened' ? '↓' : '→'} {h.parameter} · {h.reasoning.slice(0, 60)}
              </p>
            ))}
          </div>
        )}
      </section>

      <div className="border-t border-oxford/12" />

      {/* Last Cycle Report */}
      <section className="py-6">
        <h3 className="type-label-section text-oxford/60 mb-3">Last meta cycle</h3>
        {latest ? (
          <>
            <p className="type-meta text-oxford/40 mb-3">
              Cycle {latest.cycle_number} · {new Date(latest.ran_at).toLocaleString('en-GB')}
            </p>
            <div className="flex gap-6 mb-4">
              {[
                { label: 'Mutations', value: latest.mutations_applied.length },
                { label: 'Reweightings', value: latest.weight_updates.length },
                { label: 'Calibrations', value: latest.calibration_changes.length },
              ].map((s) => (
                <div key={s.label} className="text-center">
                  <p className="type-title text-oxford tabular-nums">{s.value}</p>
                  <p className="type-label-section text-oxford/60">{s.label}</p>
                </div>
              ))}
            </div>
            {latest.mutations_applied.map((m, i) => (
              <div key={i} className="mb-2">
                <p className="type-label-section text-oxford/60">{m.agent_target}</p>
                <p className="type-body-sm text-oxford/60 line-clamp-2">{m.reasoning}</p>
                <p className="type-meta text-oxford/25">{m.previous_prompt_hash} → {m.new_prompt_hash}</p>
              </div>
            ))}
            {latest.no_action_reasons.length > 0 && (
              <div className="mt-3">
                {latest.no_action_reasons.map((r, i) => (
                  <p key={i} className="type-body-sm italic text-oxford/40">{r}</p>
                ))}
              </div>
            )}
            <p className="type-meta text-oxford/40 mt-3">
              Next cycle {formatRelativeTime(latest.next_cycle_at)}
            </p>
          </>
        ) : (
          <EmptyState
            label="Last meta cycle"
            body="The meta-agent runs once there is enough signal from reviews and decisions. Cycle summary and mutations will show here after the first run completes."
          />
        )}
      </section>

      <div className="border-t border-oxford/12" />

      {/* Manual Trigger */}
      <section className="pt-6">
        <button
          onClick={handleTrigger}
          disabled={triggering || !!triggerResult}
          className="w-full py-3 type-label-tab text-oxford/60 border border-oxford/25 hover:text-oxford hover:border-oxford/40 hover:bg-oxford/[0.03] btn-interaction disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {triggering ? 'Triggering…' : triggerResult ?? 'Trigger meta cycle'}
        </button>
      </section>
    </div>
  );
}

/* ─── FUND THESIS RUNTIME ─── */
function FundThesisRuntimeTab() {
  const [data, setData] = useState<FundThesisRuntime | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => {
    setErr(null);
    fetchFundThesisRuntime()
      .then(setData)
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : 'Failed to load'));
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 90_000);
    return () => clearInterval(t);
  }, [load]);

  if (err) {
    return <p className="type-body-sm text-red-800/90">{err}</p>;
  }
  if (!data) {
    return <p className="type-label-tab text-oxford/40">Loading…</p>;
  }
  if (data.error === 'incomplete') {
    return (
      <EmptyState
        label="Fund thesis"
        body={
          data.detail?.trim()
            ? data.detail
            : 'Thesis data could not be loaded. Check Supabase connectivity and migrations.'
        }
      />
    );
  }
  if (data.mode === 'missing' || data.thesis_ready === false) {
    return (
      <EmptyState
        label="Fund thesis"
        body="No active thesis yet. Add one under Settings → Fund thesis."
      />
    );
  }
  if (data.thesis_ready !== true && data.mode !== 'rule_based' && data.mode !== 'embedding') {
    return (
      <EmptyState
        label="Fund thesis"
        body="Thesis is not ready. Open Settings → Fund thesis."
      />
    );
  }

  const st = data.alignment_stats;
  return (
    <div className="space-y-6">
      <section>
        <h3 className="type-label-section text-oxford/60 mb-2">Runtime</h3>
        <p className="type-body-sm text-oxford/60 m-0">
          Active version{' '}
          <code className="type-meta bg-oxford/[0.06] px-1 rounded break-all">{data.active_version_id}</code>
          {data.active_version_number != null ? ` · v${data.active_version_number}` : ''}
        </p>
        <p className="type-body-sm text-oxford/60 m-0 mt-1">
          Last updated:{' '}
          {data.fund_thesis_updated_at
            ? new Date(data.fund_thesis_updated_at).toLocaleString('en-GB')
            : '—'}
        </p>
        <p className="type-body-sm text-oxford/60 m-0 mt-1">
          Thesis mode:{' '}
          {data.thesis_mode === 'embedding' ? 'AI-enhanced' : 'Rule-based'}
        </p>
        <p className="type-body-sm text-oxford/60 m-0 mt-1">
          Embeddings: {data.embedding?.dimension ?? data.embedding_dimensions ?? '—'} dims ·{' '}
          {data.embedding?.model ?? data.embedding_model ?? '—'}
        </p>
      </section>
      <div className="border-t border-oxford/12" />
      <section>
        <h3 className="type-label-section text-oxford/60 mb-2">Alignment (reviewed deals, current version)</h3>
        <ul className="type-body-sm text-oxford/60 m-0 pl-4 list-disc space-y-1">
          <li>
            Matching mandate:{' '}
            {st?.pct_matching_thesis != null ? `${st.pct_matching_thesis}%` : '—'} of scored reviews
          </li>
          <li>Avg alignment score: {st?.avg_alignment_score ?? '—'}</li>
          <li>Drift vs prior version: {st?.drift_vs_previous ?? '—'}</li>
          <li>Reviews tagged with this version: {st?.reviewed_with_thesis_count ?? 0}</li>
        </ul>
      </section>
      <div className="border-t border-oxford/12" />
      <section>
        <h3 className="type-label-section text-oxford/60 mb-3">Version timeline</h3>
        {(data.version_timeline ?? []).length === 0 ? (
          <p className="type-label-tab text-oxford/40">No versions</p>
        ) : (
          <ul className="space-y-2">
            {(data.version_timeline ?? []).map((v) => (
              <li key={v.id} className="type-body-sm text-oxford/60 border-b border-oxford/8 pb-2">
                <span className="type-label-section text-oxford/50">v{v.version_number}</span>
                {v.is_active ? <span className="ml-2 type-meta text-oxford">active</span> : null}
                <span className="block type-meta text-oxford/35 mt-0.5">
                  {v.created_at ? new Date(v.created_at).toLocaleString('en-GB') : ''}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

/* ─── MAIN COMPONENT ─── */
export default function SystemIntelligence(props: SystemIntelligenceProps) {
  const [activeTab, setActiveTab] = useState<Tab>('escalations');
  const reduceMotion = usePrefersReducedMotion();

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* Tab bar — same as PanelShell / SettingsPage */}
      <nav className={SYSTEM_INTEL_TAB_BAR_CLASS} aria-label="Tabs">
        {TABS.map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={`${SYSTEM_INTEL_TAB_BUTTON_CLASS} ${
                isActive ? PANEL_TAB_ACTIVE_CLASS : PANEL_TAB_INACTIVE_CLASS
              }`}
              aria-selected={isActive}
            >
              {tab.label}
            </button>
          );
        })}
      </nav>

      {/* Content */}
      <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-5">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={transitionOrReduced(reduceMotion, {
              duration: tokens.motion.duration.short,
              ease: tokens.motion.ease,
            })}
          >
            {activeTab === 'signals' && <SignalsTab signals={props.signals} />}
            {activeTab === 'escalations' && (
              <EscalationsTab
                escalations={props.escalations}
                onResolved={props.onEscalationResolved}
                onOpenMemo={props.onOpenEscalationMemo}
              />
            )}
            {activeTab === 'analytics' && (
              <AnalyticsTab
                rejection={props.rejectionAnalytics}
                watchlist={props.watchlistAnalytics}
                concentration={props.concentrationAnalytics}
              />
            )}
            {activeTab === 'thesis' && <FundThesisRuntimeTab />}
            {activeTab === 'meta' && (
              <MetaAgentTab reports={props.metaReports} weights={props.scoutWeights} calibration={props.calibrationState} />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
