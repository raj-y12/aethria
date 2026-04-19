import { useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { tokens } from '../design-system/tokens';
import type {
  SignalItem, RejectionAnalytics, WatchlistAnalytics,
  ConcentrationAnalytics, MetaCycleReport, ScoutWeights, CalibrationState,
} from '../types/startup';
import { triggerMetaCycle } from '../api/meta';
import { transitionOrReduced } from '../design-system/motion';
import { UI_FILTER_TOOLBAR_LABEL } from '../design-system/ui-text';
import { usePrefersReducedMotion } from '../hooks';
import EmptyState from './EmptyState';
import { fetchFundThesisRuntime, type FundThesisRuntime } from '../api/fundThesis';

type Tab = 'signals' | 'analytics' | 'thesis' | 'meta';
const TABS: { key: Tab; label: string }[] = [
  { key: 'signals', label: 'Signals' },
  { key: 'analytics', label: 'Analytics' },
  { key: 'thesis', label: 'Thesis' },
  { key: 'meta', label: 'Meta' },
];

interface SystemIntelligenceProps {
  signals: SignalItem[];
  rejectionAnalytics: RejectionAnalytics;
  watchlistAnalytics: WatchlistAnalytics;
  concentrationAnalytics: ConcentrationAnalytics;
  metaReports: MetaCycleReport[];
  scoutWeights: ScoutWeights;
  calibrationState: CalibrationState;
  onClose?: () => void;
}

function TacticalBar({ pct, delay = 0 }: { pct: number; delay?: number }) {
  const reduceMotion = usePrefersReducedMotion();
  return (
    <div className="w-full h-[1px] bg-oxford/10 relative overflow-hidden">
      <motion.div
        className="absolute inset-0 h-full bg-oxford/40 origin-left"
        initial={reduceMotion ? { scaleX: Math.min(1, Math.max(0, pct / 100)) } : { scaleX: 0 }}
        animate={{ scaleX: Math.min(1, Math.max(0, pct / 100)) }}
        transition={transitionOrReduced(reduceMotion, {
          duration: 1.2,
          delay: reduceMotion ? 0 : delay,
          ease: [0.16, 1, 0.3, 1],
        })}
      />
    </div>
  );
}

/* ─── ROW WRAPPER ─── */
function RowWrapper({ children, index, onClick, isSelected }: { children: React.ReactNode; index: number; onClick?: () => void; isSelected?: boolean }) {
  const reduceMotion = usePrefersReducedMotion();
  return (
    <motion.div
      initial={reduceMotion ? {} : { opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: Math.min(index * 0.04, 0.4), duration: 0.6, ease: tokens.motion.ease }}
      className={`group relative border-b border-oxford/[0.06] py-phi-5 px-phi-4 transition-all duration-700 ease-smooth ${onClick ? 'cursor-pointer' : ''
        } ${isSelected ? 'bg-registerTint' : 'hover:bg-oxford/[0.02]'}`}
      onClick={onClick}
    >
      <div className="grid grid-cols-1 gap-phi-5 items-start lg:grid-cols-[76px_minmax(0,1fr)_max-content] 2xl:grid-cols-[100px_minmax(0,1fr)_max-content]">
        {children}
      </div>
    </motion.div>
  );
}

/* ─── SIGNALS ─── */
function SignalsTab({ signals }: { signals: SignalItem[] }) {
  if (signals.length === 0) {
    return (
      <div className="py-phi-8 px-phi-4 flex items-center justify-center">
        <EmptyState label="Signals" body="No high-priority events detected in the last cycle." />
      </div>
    );
  }
  return (
    <div className="flex flex-col relative">
      {signals.map((sig, i) => (
        <RowWrapper key={sig.id ?? i} index={i}>
          {/* Index */}
          <div className="flex flex-col gap-phi-3 min-w-0">
            <span className="font-mono type-label-section text-oxford/20 group-hover:text-oxford/50 transition-colors duration-500 tabular-nums">
              {(i + 1).toString().padStart(2, '0')}
            </span>
            <div className="flex flex-col gap-0.5">
              <span className="type-meta text-oxford/30 uppercase tracking-tighter">Time</span>
              <span className="font-mono type-meta text-oxford/50 tabular-nums">
                {sig.detected_at ? new Date(sig.detected_at).toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit' }) : '--:--'}
              </span>
            </div>
          </div>

          {/* Content */}
          <div className="flex min-w-0 flex-col gap-phi-4">
            <div className="flex items-center gap-2">
              <span className="type-meta text-oxford/40 uppercase tracking-widest">{sig.signal_type.replace(/_/g, ' ')}</span>
              <span className="w-1.5 h-1.5 border border-oxford/20 rotate-45" />
              <span className="type-label-tab text-oxford/40">{sig.startup_id?.slice(0, 8) ?? 'Unknown'}</span>
            </div>
            <p className="type-body text-oxford/60 leading-relaxed italic border-l-2 border-oxford/[0.06] pl-phi-4 max-w-2xl">
              {sig.description}
            </p>
          </div>

          {/* Meta */}
          <div className="flex min-w-0 flex-col items-start gap-phi-5 lg:items-end">
            <div className="flex flex-col items-start lg:items-end gap-phi-2">
              <span className="type-meta text-oxford/30 uppercase tracking-widest">Source</span>
              <span className="type-meta text-oxford/50 uppercase tracking-tighter">
                {sig.tracker_agent_id ?? sig.source ?? 'System'}
              </span>
            </div>
            <div className="flex w-full flex-col items-start gap-phi-1 border-t border-oxford/[0.06] pt-phi-4 lg:w-auto lg:items-end">
              <span className="type-meta text-oxford/30 uppercase">Date</span>
              <span className="font-mono type-meta text-oxford/50 tabular-nums">
                {sig.detected_at ? new Date(sig.detected_at).toLocaleDateString('en-GB') : ''}
              </span>
            </div>
          </div>
        </RowWrapper>
      ))}
    </div>
  );
}

/* ─── SECTION WRAPPER ─── */
function TabSection({ title, label, children }: { title: string; label?: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-phi-4 px-phi-4 py-phi-5 border-b border-oxford/[0.06] last:border-0">
      <div className="flex items-center justify-between border-b border-oxford/[0.06] pb-phi-3">
        <h3 className="type-meta text-oxford/50 uppercase tracking-[0.18em]">{title}</h3>
        {label && <span className="type-meta text-oxford/30">{label}</span>}
      </div>
      {children}
    </section>
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
    <div className="flex flex-col">
      <TabSection title="Rejection Patterns" label="Historical">
        {rejection.most_common_red_flags.length === 0 ? (
          <p className="type-meta text-oxford/20 uppercase tracking-[0.18em]">No rejection data yet</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-phi-5 gap-y-phi-4">
            {rejection.most_common_red_flags.slice(0, 6).map((rf, i) => (
              <div key={rf.flag} className="flex flex-col gap-2">
                <div className="flex justify-between items-baseline">
                  <span className="type-meta text-oxford/40 uppercase tracking-widest">{rf.flag.replace(/_/g, ' ')}</span>
                  <span className="font-mono type-meta text-oxford/60 tabular-nums">{rf.count}</span>
                </div>
                <TacticalBar pct={(rf.count / maxRedFlag) * 100} delay={i * 0.05} />
              </div>
            ))}
          </div>
        )}
      </TabSection>

      <TabSection title="Watchlist" label="Health">
        <div className="flex flex-wrap gap-phi-6">
          {[
            { label: 'Total', value: watchlist.total },
            { label: 'Stale', value: watchlist.stale },
            { label: 'Avg Days', value: Math.round(watchlist.avg_days) },
          ].map((s) => (
            <div key={s.label} className="flex flex-col gap-1">
              <span className="font-mono font-semibold text-4xl text-oxford tracking-tighter tabular-nums">{s.value}</span>
              <span className="type-meta text-oxford/30 uppercase tracking-[0.14em]">{s.label}</span>
            </div>
          ))}
        </div>
      </TabSection>

      <TabSection title="Sector Concentration" label="Distribution">
        {sectors.length === 0 ? (
          <p className="type-meta text-oxford/20 uppercase tracking-[0.18em]">No concentration data yet</p>
        ) : (
          <div className="flex flex-col gap-phi-4">
            {sectors.map(([sector, data], i) => (
              <div key={sector} className="grid grid-cols-[100px_1fr_44px] gap-phi-4 items-center">
                <span className="type-meta text-oxford/60 uppercase tracking-widest truncate">{sector}</span>
                <TacticalBar pct={(data.count / maxSector) * 100} delay={i * 0.05} />
                <span className="font-mono type-meta text-oxford/40 tabular-nums text-right">{data.pct_of_total}%</span>
              </div>
            ))}
          </div>
        )}
      </TabSection>
    </div>
  );
}

/* ─── FUND THESIS ─── */
function InstitutionalMandateTab() {
  const [data, setData] = useState<FundThesisRuntime | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => {
    fetchFundThesisRuntime()
      .then(setData)
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : 'Failed to load'));
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 120_000);
    return () => clearInterval(t);
  }, [load]);

  if (err) {
    return (
      <div className="py-phi-8 px-phi-4 flex items-center justify-center">
        <EmptyState label="Fund Thesis" body="Could not load thesis data. Check your API connection and try again." />
      </div>
    );
  }

  if (!data) return (
    <div className="px-phi-4 py-10">
      <p className="type-meta text-oxford/20 uppercase tracking-widest">Loading...</p>
    </div>
  );

  if (data.mode === 'missing' || (!data.parsed_json && data.thesis_ready === false)) {
    return (
      <div className="py-phi-8 px-phi-4 flex items-center justify-center">
        <EmptyState label="Fund Thesis" body="No active thesis configured. Set up your investment mandate in Settings to enable thesis-aligned scouting." />
      </div>
    );
  }

  const pj = data.parsed_json ?? {};
  const sectors = Array.isArray(pj.sectors) ? (pj.sectors as string[]) : [];
  const stages = Array.isArray(pj.stage_focus) ? (pj.stage_focus as string[]) : [];

  return (
    <div className="flex flex-col">
      <TabSection title="Portfolio Mandate" label={`v${data.active_version_number ?? '01'}`}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-phi-5">
          <div className="flex flex-col gap-phi-5">
            <div className="flex flex-col gap-2">
              <span className="type-meta text-oxford/30 uppercase tracking-widest">Target Sectors</span>
              <div className="flex flex-wrap gap-2 mt-1">
                {sectors.map(s => <span key={s} className="type-meta border border-oxford/10 px-2 py-1 text-oxford/60">{s}</span>)}
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <span className="type-meta text-oxford/30 uppercase tracking-widest">Stage Focus</span>
              <div className="flex flex-wrap gap-2 mt-1">
                {stages.map(s => <span key={s} className="type-meta border border-oxford/10 px-2 py-1 text-oxford/60">{s}</span>)}
              </div>
            </div>
          </div>
          <div className="flex flex-col gap-phi-3 p-phi-4 bg-oxford/[0.02] border border-oxford/[0.06]">
            <span className="type-meta text-oxford/30 uppercase tracking-widest">Agent Directive</span>
            <p className="type-body text-oxford/60 leading-relaxed italic">
              Scouts are calibrated to prioritize {sectors[0] || 'core sector'} opportunities within {stages[0] || 'targeted stage'} cycles.
              Mandate mode: <span className="text-oxford/80">{data.thesis_mode === 'embedding' ? 'AI Enhanced' : 'Rule Based'}</span>.
            </p>
          </div>
        </div>
      </TabSection>

      <TabSection title="Alignment">
        <div className="grid grid-cols-3 gap-phi-4">
          <div className="border-l border-oxford/10 pl-phi-3 py-1">
            <span className="block font-mono font-semibold text-2xl text-oxford tabular-nums">{data.alignment_stats?.pct_matching_thesis ?? '--'}%</span>
            <span className="type-meta text-oxford/30 uppercase text-[9px]">Mandate match</span>
          </div>
          <div className="border-l border-oxford/10 pl-phi-3 py-1">
            <span className="block font-mono font-semibold text-2xl text-oxford tabular-nums">{data.alignment_stats?.avg_alignment_score ?? '--'}</span>
            <span className="type-meta text-oxford/30 uppercase text-[9px]">Mean alignment</span>
          </div>
          <div className="border-l border-oxford/10 pl-phi-3 py-1">
            <span className="block font-mono font-semibold text-2xl text-oxford tabular-nums">{data.alignment_stats?.drift_vs_previous ?? '0.00'}</span>
            <span className="type-meta text-oxford/30 uppercase text-[9px]">Drift</span>
          </div>
        </div>
      </TabSection>
    </div>
  );
}

/* ─── META AGENT ─── */
function MetaCommandTab({ reports, weights, calibration }: {
  reports: MetaCycleReport[]; weights: ScoutWeights; calibration: CalibrationState;
}) {
  const [triggering, setTriggering] = useState(false);
  const handleTrigger = async () => {
    setTriggering(true);
    try { await triggerMetaCycle(); } finally { setTriggering(false); }
  };

  const lastReport = reports.length > 0 ? reports[0] : null;

  return (
    <div className="flex flex-col">
      {lastReport ? (
        <TabSection title="Last Cycle" label={`Cycle ${lastReport.cycle_number}`}>
          <div className="flex flex-wrap gap-phi-6">
            {[
              { label: 'Ran', value: new Date(lastReport.ran_at).toLocaleDateString('en-GB') },
              { label: 'Mutations', value: (lastReport.mutations_applied ?? []).length },
              { label: 'Weight updates', value: (lastReport.weight_updates ?? []).length },
            ].map((s) => (
              <div key={s.label} className="flex flex-col gap-1">
                <span className="font-mono font-semibold text-2xl text-oxford tracking-tighter tabular-nums">{s.value}</span>
                <span className="type-meta text-oxford/30 uppercase tracking-[0.14em]">{s.label}</span>
              </div>
            ))}
          </div>
          {lastReport.no_action_reasons.length > 0 && (
            <div className="mt-phi-4 border-l-2 border-oxford/[0.06] pl-phi-4">
              {lastReport.no_action_reasons.map((r, i) => (
                <p key={i} className="type-meta text-oxford/40 leading-relaxed">{r}</p>
              ))}
            </div>
          )}
        </TabSection>
      ) : (
        <TabSection title="Last Cycle">
          <p className="type-meta text-oxford/20 uppercase tracking-[0.18em]">No cycles run yet</p>
        </TabSection>
      )}
      <TabSection title="Scout Allocation" label="Weights">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-phi-5 gap-y-phi-4">
          {[
            ['Market Scout', weights.MarketDrivenScout],
            ['Technical Scout', weights.BuilderTechnicalScout],
            ['Pain Point Scout', weights.PainPointScout],
            ['Contrarian Scout', weights.ContrarianScout],
          ].map(([name, w], i) => (
            <div key={name} className="flex flex-col gap-2">
              <div className="flex justify-between items-baseline">
                <span className="type-meta text-oxford/40 uppercase tracking-widest">{name}</span>
                <span className="font-mono type-meta text-oxford/60 tabular-nums">{Math.round(w * 100)}%</span>
              </div>
              <TacticalBar pct={w * 100} delay={i * 0.1} />
            </div>
          ))}
        </div>
      </TabSection>

      <TabSection title="Calibration Log">
        {calibration.calibration_history.length === 0 ? (
          <p className="type-meta text-oxford/20 uppercase tracking-[0.18em]">No calibration history yet</p>
        ) : (
          <div className="flex flex-col border border-oxford/[0.06] bg-oxford/[0.01]">
            {calibration.calibration_history.slice(-5).reverse().map((h, i) => (
              <div key={i} className="grid grid-cols-[100px_1fr] gap-phi-4 border-b border-oxford/[0.06] last:border-0 p-phi-4 items-start">
                <span className={`type-meta text-[9px] uppercase px-1 py-0.5 border ${h.direction === 'tightened' ? 'border-escalation/20 text-escalation/60' : 'border-oxford/10 text-oxford/40'} text-center`}>
                  {h.direction}
                </span>
                <div className="flex flex-col gap-1">
                  <span className="type-meta text-oxford/60 uppercase tracking-tight">{h.parameter.replace(/_/g, ' ')}</span>
                  <p className="type-meta text-oxford/30 leading-relaxed font-mono">{h.reasoning}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </TabSection>

      <div className="px-phi-4 py-phi-5 flex justify-end">
        <button
          onClick={handleTrigger}
          disabled={triggering}
          className="type-meta border border-oxford/20 px-phi-5 py-phi-3 text-oxford/40 hover:text-oxford hover:border-oxford/60 transition-colors uppercase tracking-[0.18em] btn-interaction"
        >
          {triggering ? 'Running...' : 'Run Correction Cycle'}
        </button>
      </div>
    </div>
  );
}

/* ─── MAIN COMPONENT ─── */
export default function SystemIntelligence(props: SystemIntelligenceProps) {
  const [activeTab, setActiveTab] = useState<Tab>('signals');
  const reduceMotion = usePrefersReducedMotion();

  return (
    <div className="w-full font-sans bg-paper selection:bg-oxford selection:text-paper min-h-full">
      <div className="sticky top-0 z-20 bg-paper/90 backdrop-blur-md border-b border-oxford/[0.06] px-phi-4 py-phi-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-phi-4">
            <span className={UI_FILTER_TOOLBAR_LABEL}>System</span>
            <div className="flex items-center gap-1">
              {TABS.map((tab) => {
                const isActive = activeTab === tab.key;
                return (
                  <button
                    key={tab.key}
                    type="button"
                    onClick={() => setActiveTab(tab.key)}
                    className={`type-label-tab px-3 py-1.5 transition-all duration-300 border-b ${isActive ? 'border-oxford text-oxford bg-oxford/5' : 'border-transparent text-oxford/30 hover:text-oxford/60'
                      }`}
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>
          {props.onClose && (
            <button
              type="button"
              onClick={props.onClose}
              className="type-label-tab text-oxford/40 hover:text-oxford transition-colors border-l border-oxford/10 pl-phi-4"
              aria-label="Hide system intelligence"
            >
              Close
            </button>
          )}
        </div>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={transitionOrReduced(reduceMotion, { duration: 0.3, ease: 'circOut' })}
        >
          {activeTab === 'signals' && <SignalsTab signals={props.signals} />}
          {activeTab === 'analytics' && (
            <AnalyticsTab
              rejection={props.rejectionAnalytics}
              watchlist={props.watchlistAnalytics}
              concentration={props.concentrationAnalytics}
            />
          )}
          {activeTab === 'thesis' && <InstitutionalMandateTab />}
          {activeTab === 'meta' && (
            <MetaCommandTab reports={props.metaReports} weights={props.scoutWeights} calibration={props.calibrationState} />
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
