import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { tokens } from '../design-system/tokens';
import type {
  SignalItem, EscalationItem, RejectionAnalytics, WatchlistAnalytics,
  ConcentrationAnalytics, MetaCycleReport, ScoutWeights, CalibrationState,
} from '../types/startup';
import { resolveEscalation } from '../api/escalations';
import { triggerMetaCycle } from '../api/meta';

type Tab = 'signals' | 'escalations' | 'analytics' | 'meta';
const TABS: { key: Tab; label: string }[] = [
  { key: 'signals', label: 'Signals' },
  { key: 'escalations', label: 'Escalations' },
  { key: 'analytics', label: 'Analytics' },
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
  return (
    <div className="w-full h-1.5" style={{ backgroundColor: 'rgba(0,33,71,0.08)' }}>
      <motion.div
        className="h-full"
        style={{ backgroundColor: 'rgba(0,33,71,0.2)' }}
        initial={{ width: 0 }}
        animate={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
        transition={{ duration: 0.4, delay, ease: tokens.motion.ease }}
      />
    </div>
  );
}

/* ─── SIGNALS ─── */
function SignalsTab({ signals }: { signals: SignalItem[] }) {
  if (signals.length === 0) {
    return <p className="text-center py-12 font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/30">No signals detected</p>;
  }
  return (
    <div className="space-y-0">
      {signals.map((sig, i) => (
        <div key={sig.id ?? i} className="py-3 border-b border-oxford/[0.06]">
          <div className="flex items-baseline gap-2 mb-1">
            <span className="font-sans text-[13px] font-semibold text-oxford">{sig.startup_id?.slice(0, 8) ?? 'Unknown'}</span>
            <span className="font-mono text-[9px] uppercase tracking-[0.16em] text-oxford/50">{sig.signal_type.replace('_', ' ')}</span>
          </div>
          <p className="font-sans text-[13px] text-oxford/70 leading-relaxed line-clamp-2">{sig.description}</p>
          <p className="font-mono text-[9px] text-oxford/40 mt-1">
            {sig.tracker_agent_id ?? sig.source ?? ''} · {sig.detected_at ? new Date(sig.detected_at).toLocaleDateString('en-GB') : ''}
          </p>
        </div>
      ))}
    </div>
  );
}

/* ─── ESCALATIONS ─── */
function EscalationsTab({ escalations, onResolved }: { escalations: EscalationItem[]; onResolved?: () => void }) {
  const pending = escalations.filter((e) => !e.human_resolution);
  if (pending.length === 0) {
    return <p className="text-center py-12 font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/30">No pending escalations</p>;
  }
  return (
    <div className="space-y-0">
      {pending.map((esc) => (
        <EscalationCard key={esc.id} escalation={esc} onResolved={onResolved} />
      ))}
    </div>
  );
}

function EscalationCard({ escalation, onResolved }: { escalation: EscalationItem; onResolved?: () => void }) {
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

  if (resolved) {
    return (
      <motion.div
        initial={{ opacity: 1, height: 'auto' }}
        animate={{ opacity: 0, height: 0 }}
        transition={{ duration: 0.25, ease: tokens.motion.ease }}
        className="overflow-hidden"
      >
        <p className="py-4 text-center font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60">Resolved</p>
      </motion.div>
    );
  }

  return (
    <div className="py-4 border-b border-oxford/[0.06] border-l-2 border-l-oxford pl-4">
      <p className="font-sans text-[14px] font-semibold text-oxford">{escalation.scout?.name ?? escalation.id}</p>
      <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-oxford/50 mt-1">
        {escalation.scout?.sector ?? ''} · Conviction {escalation.partner?.confidence ?? '—'}/10
      </p>
      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-oxford mt-2">Awaiting human review</p>
      {escalation.partner?.rationale && (
        <p className="font-sans text-[13px] text-oxford/70 mt-2 leading-relaxed line-clamp-3">{escalation.partner.rationale}</p>
      )}
      {escalation.partner?.llm_fallback_reason && (
        <p className="font-sans text-[12px] italic text-oxford/50 mt-1">{escalation.partner.llm_fallback_reason}</p>
      )}
      {!resolving ? (
        <div className="flex gap-0 mt-3">
          {(['YES', 'NO', 'MAYBE'] as const).map((d) => (
            <button
              key={d}
              onClick={() => setResolving(d)}
              className="flex-1 py-2 font-mono text-[9px] uppercase tracking-[0.16em] text-oxford/60 border border-oxford/[0.15] hover:text-oxford hover:border-oxford/30 transition-colors"
            >
              {d === 'YES' ? 'Advance' : d === 'NO' ? 'Pass' : 'Hold'}
            </button>
          ))}
        </div>
      ) : (
        <div className="mt-3 space-y-2">
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Notes (optional)"
            className="w-full bg-transparent border border-oxford/[0.15] p-2 font-sans text-[13px] text-oxford placeholder:text-oxford/30 outline-none focus:border-oxford/30 resize-none rounded-none"
            rows={2}
          />
          <div className="flex gap-2">
            <button
              onClick={handleResolve}
              className="flex-1 py-2 font-mono text-[9px] uppercase tracking-[0.22em] bg-oxford text-paper"
            >
              Confirm {resolving === 'YES' ? 'Advance' : resolving === 'NO' ? 'Pass' : 'Hold'}
            </button>
            <button
              onClick={() => { setResolving(null); setNotes(''); }}
              className="py-2 px-3 font-mono text-[9px] uppercase tracking-[0.22em] text-oxford/50 border border-oxford/[0.15]"
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

  return (
    <div className="space-y-0">
      {/* Rejection Patterns */}
      <section className="pb-6">
        <h3 className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60 mb-3">Rejection patterns</h3>
        {rejection.most_common_red_flags.slice(0, 6).map((rf, i) => (
          <div key={rf.flag} className="flex items-center gap-2 mb-1">
            <span className="font-sans text-[11px] text-oxford/60 w-32 truncate shrink-0">{rf.flag}</span>
            <div className="flex-1"><BarFill pct={(rf.count / maxRedFlag) * 100} delay={i * 0.05} /></div>
            <span className="font-mono text-[10px] text-oxford/40 tabular-nums w-6 text-right">{rf.count}</span>
          </div>
        ))}
        {rejection.most_common_red_flags.length === 0 && (
          <p className="font-mono text-[10px] text-oxford/30">No rejection data yet</p>
        )}
      </section>

      <div className="border-t border-oxford/[0.10]" />

      {/* Watchlist Health */}
      <section className="py-6">
        <h3 className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60 mb-3">Watchlist health</h3>
        <div className="flex gap-6">
          {[
            { label: 'Total', value: watchlist.total },
            { label: 'Stale', value: watchlist.stale },
            { label: 'Avg days', value: Math.round(watchlist.avg_days) },
          ].map((s) => (
            <div key={s.label} className="text-center">
              <p className="font-display text-[24px] text-oxford tabular-nums">{s.value}</p>
              <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-oxford/50">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      <div className="border-t border-oxford/[0.10]" />

      {/* Sector Concentration */}
      <section className="pt-6">
        <h3 className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60 mb-3">Pipeline concentration</h3>
        {sectors.map(([sector, data], i) => (
          <div key={sector} className="flex items-center gap-2 mb-1">
            <span className="font-sans text-[11px] text-oxford/60 w-36 truncate shrink-0">
              {sector}
              {sector === concentration.most_concentrated_sector && (
                <span className="font-mono text-[8px] text-oxford/40 ml-1">concentrated</span>
              )}
            </span>
            <div className="flex-1"><BarFill pct={(data.count / maxSector) * 100} delay={i * 0.05} /></div>
            <span className="font-mono text-[10px] text-oxford/40 tabular-nums w-12 text-right">{data.count} · {data.pct_of_total}%</span>
          </div>
        ))}
        {sectors.length === 0 && <p className="font-mono text-[10px] text-oxford/30">No pipeline data yet</p>}
        {concentration.last_updated && (
          <p className="font-mono text-[8px] text-oxford/30 mt-3">Updated {new Date(concentration.last_updated).toLocaleString('en-GB')}</p>
        )}
      </section>
    </div>
  );
}

/* ─── META-AGENT ─── */
function MetaAgentTab({ reports, weights, calibration }: {
  reports: MetaCycleReport[]; weights: ScoutWeights; calibration: CalibrationState;
}) {
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
      {/* Scout Weights */}
      <section className="pb-6">
        <h3 className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60 mb-3">Scout allocation</h3>
        {weightEntries.map(([name, w], i) => (
          <div key={name} className="flex items-center gap-2 mb-1.5">
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-oxford/60 w-20 shrink-0">{name}</span>
            <div className="flex-1"><BarFill pct={w * 100} delay={i * 0.05} /></div>
            <span className="font-mono text-[10px] text-oxford/50 tabular-nums w-8 text-right">{Math.round(w * 100)}%</span>
          </div>
        ))}
      </section>

      <div className="border-t border-oxford/[0.10]" />

      {/* Calibration State */}
      <section className="py-6">
        <h3 className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60 mb-3">Calibration state</h3>
        {calibration.confidence_threshold_override == null && calibration.reviewer_weak_threshold_override == null ? (
          <p className="font-mono text-[10px] text-oxford/40">Running at defaults</p>
        ) : (
          <div className="space-y-1">
            {calibration.confidence_threshold_override != null && (
              <p className="font-mono text-[10px] text-oxford/60">
                Confidence threshold: {calibration.confidence_threshold_override}
              </p>
            )}
            {calibration.reviewer_weak_threshold_override != null && (
              <p className="font-mono text-[10px] text-oxford/60">
                Weak threshold: {calibration.reviewer_weak_threshold_override}
              </p>
            )}
          </div>
        )}
        {calibration.last_calibrated_at && (
          <p className="font-mono text-[8px] text-oxford/30 mt-2">
            Last calibrated: {new Date(calibration.last_calibrated_at).toLocaleString('en-GB')}
          </p>
        )}
        {calibration.calibration_history.length > 0 && (
          <div className="mt-3 space-y-1">
            {calibration.calibration_history.slice(-5).reverse().map((h, i) => (
              <p key={i} className="font-mono text-[9px] text-oxford/40">
                {h.direction === 'tightened' ? '↑' : h.direction === 'loosened' ? '↓' : '→'} {h.parameter} · {h.reasoning.slice(0, 60)}
              </p>
            ))}
          </div>
        )}
      </section>

      <div className="border-t border-oxford/[0.10]" />

      {/* Last Cycle Report */}
      <section className="py-6">
        <h3 className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60 mb-3">Last meta cycle</h3>
        {latest ? (
          <>
            <p className="font-mono text-[9px] text-oxford/40 mb-3">
              Cycle {latest.cycle_number} · {new Date(latest.ran_at).toLocaleString('en-GB')}
            </p>
            <div className="flex gap-6 mb-4">
              {[
                { label: 'Mutations', value: latest.mutations_applied.length },
                { label: 'Reweightings', value: latest.weight_updates.length },
                { label: 'Calibrations', value: latest.calibration_changes.length },
              ].map((s) => (
                <div key={s.label} className="text-center">
                  <p className="font-display text-[24px] text-oxford tabular-nums">{s.value}</p>
                  <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-oxford/50">{s.label}</p>
                </div>
              ))}
            </div>
            {latest.mutations_applied.map((m, i) => (
              <div key={i} className="mb-2">
                <p className="font-mono text-[10px] text-oxford/60">{m.agent_target}</p>
                <p className="font-sans text-[12px] text-oxford/50 line-clamp-2">{m.reasoning}</p>
                <p className="font-mono text-[8px] text-oxford/30">{m.previous_prompt_hash} → {m.new_prompt_hash}</p>
              </div>
            ))}
            {latest.no_action_reasons.length > 0 && (
              <div className="mt-3">
                {latest.no_action_reasons.map((r, i) => (
                  <p key={i} className="font-sans text-[11px] italic text-oxford/40">{r}</p>
                ))}
              </div>
            )}
            <p className="font-mono text-[9px] text-oxford/40 mt-3">
              Next cycle {formatRelativeTime(latest.next_cycle_at)}
            </p>
          </>
        ) : (
          <p className="font-mono text-[10px] text-oxford/30">No cycles completed yet</p>
        )}
      </section>

      <div className="border-t border-oxford/[0.10]" />

      {/* Manual Trigger */}
      <section className="pt-6">
        <button
          onClick={handleTrigger}
          disabled={triggering || !!triggerResult}
          className="w-full py-3 font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60 border border-oxford/[0.15] hover:text-oxford hover:border-oxford/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {triggering ? 'Triggering…' : triggerResult ?? 'Trigger meta cycle'}
        </button>
      </section>
    </div>
  );
}

/* ─── MAIN COMPONENT ─── */
export default function SystemIntelligence(props: SystemIntelligenceProps) {
  const [activeTab, setActiveTab] = useState<Tab>('signals');

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* Tab bar */}
      <div className="flex-none flex gap-0 border-b border-oxford/[0.06] px-4">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`py-3 px-3 font-mono text-[9px] uppercase tracking-[0.16em] transition-colors border-b-2 ${
              activeTab === tab.key
                ? 'text-oxford border-oxford'
                : 'text-oxford/40 border-transparent hover:text-oxford/60'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-y-auto no-scrollbar p-4">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15, ease: tokens.motion.ease }}
          >
            {activeTab === 'signals' && <SignalsTab signals={props.signals} />}
            {activeTab === 'escalations' && <EscalationsTab escalations={props.escalations} onResolved={props.onEscalationResolved} />}
            {activeTab === 'analytics' && (
              <AnalyticsTab
                rejection={props.rejectionAnalytics}
                watchlist={props.watchlistAnalytics}
                concentration={props.concentrationAnalytics}
              />
            )}
            {activeTab === 'meta' && (
              <MetaAgentTab reports={props.metaReports} weights={props.scoutWeights} calibration={props.calibrationState} />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
