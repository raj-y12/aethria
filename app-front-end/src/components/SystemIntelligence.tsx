import { useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { tokens } from '../design-system/tokens';
import type {
  Startup, SignalItem, RejectionAnalytics, WatchlistAnalytics,
  ConcentrationAnalytics, MetaCycleReport, ScoutWeights, CalibrationState,
} from '../types/startup';
import { triggerMetaCycle } from '../api/meta';
import { transitionOrReduced } from '../design-system/motion';
import { UI_FILTER_TOOLBAR_LABEL } from '../design-system/ui-text';
import { usePrefersReducedMotion } from '../hooks';
import EmptyState from './EmptyState';
import { fetchFundThesisRuntime, type FundThesisRuntime } from '../api/fundThesis';

type Tab = 'signals' | 'analytics' | 'decisions' | 'thesis' | 'meta';
const TABS: { key: Tab; label: string }[] = [
  { key: 'signals', label: 'Signals' },
  { key: 'analytics', label: 'Analytics' },
  { key: 'decisions', label: 'Decisions' },
  { key: 'thesis', label: 'Thesis' },
  { key: 'meta', label: 'Meta' },
];

interface SystemIntelligenceProps {
  startups: Startup[];
  signals: SignalItem[];
  rejectionAnalytics: RejectionAnalytics;
  watchlistAnalytics: WatchlistAnalytics;
  concentrationAnalytics: ConcentrationAnalytics;
  metaReports: MetaCycleReport[];
  scoutWeights: ScoutWeights;
  calibrationState: CalibrationState;
  onClose?: () => void;
}

const FilterButton = ({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) => (
  <button
    type="button"
    onClick={onClick}
    className={`type-meta uppercase tracking-[0.12em] min-h-[36px] px-phi-3 transition-[color,border-color,background-color] duration-200 border-b-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 ${active ? 'border-oxford text-oxford' : 'border-transparent text-oxford/40 hover:text-oxford/70'
      }`}
  >
    {label}
  </button>
);

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
      transition={{ delay: Math.min(index * 0.03, 0.3), duration: 0.4, ease: tokens.motion.ease }}
      className={`group relative border-b border-oxford/[0.06] py-phi-3 px-phi-4 transition-colors duration-200 ease-smooth ${onClick ? 'cursor-pointer' : ''
        } ${isSelected ? 'bg-registerTint' : 'hover:bg-oxford/[0.02]'}`}
      onClick={onClick}
    >
      <div className="grid grid-cols-1 gap-phi-3 items-start lg:grid-cols-[26px_minmax(0,1fr)_auto]">
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
          <div className="flex flex-col gap-phi-2 min-w-0">
            <span className="type-meta text-oxford/20 group-hover:text-oxford/40 transition-colors tabular-nums">
              {(i + 1).toString().padStart(2, '0')}
            </span>
            <div className="flex flex-col gap-phi-1">
              <span className="type-meta uppercase tracking-[0.12em] text-oxford/35">Time</span>
              <span className="font-mono type-meta text-oxford/50 tabular-nums">
                {sig.detected_at ? new Date(sig.detected_at).toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit' }) : '--:--'}
              </span>
            </div>
          </div>

          {/* Content */}
          <div className="flex min-w-0 flex-col gap-phi-2">
            <div className="flex items-center gap-phi-2">
              <span className="type-meta text-oxford/40">{sig.signal_type.replace(/_/g, ' ')}</span>
              <span className="type-meta text-oxford/20">·</span>
              <span className="type-meta text-oxford/40">{sig.startup_id?.slice(0, 8) ?? 'Unknown'}</span>
            </div>
            <p className="type-note text-oxford/62 leading-relaxed max-w-2xl">
              {sig.description}
            </p>
          </div>

          {/* Meta */}
          <div className="flex min-w-0 flex-col items-start gap-phi-3 lg:items-end">
            <div className="flex flex-col items-start lg:items-end gap-phi-2">
              <span className="type-meta uppercase tracking-[0.12em] text-oxford/35">Source</span>
              <span className="type-meta text-oxford/50">
                {sig.tracker_agent_id ?? sig.source ?? 'System'}
              </span>
            </div>
            <div className="flex w-full flex-col items-start gap-phi-1 border-t border-oxford/[0.06] pt-phi-2 lg:w-auto lg:items-end">
              <span className="type-meta uppercase tracking-[0.12em] text-oxford/35">Date</span>
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

/* ─── DECISIONS ─── */
function DecisionsTab({ startups }: { startups: Startup[] }) {
  const decisions = startups
    .filter((startup) => startup.human_resolution?.decision)
    .map((startup) => {
      const raw = startup.human_resolution?.decision;
      const mapped =
        raw === 'YES'
          ? 'Invest'
          : raw === 'MAYBE'
            ? 'Monitor'
            : 'Pass';
      return {
        id: startup.id,
        name: startup.scout?.name?.trim() || startup.id,
        decision: mapped,
        notes: startup.human_resolution?.notes?.trim() ?? '',
        resolvedAt: startup.human_resolution?.resolved_at,
      };
    });

  if (decisions.length === 0) {
    return (
      <div className="py-phi-8 px-phi-4 flex items-center justify-center">
        <EmptyState label="Decisions" body="No manual decisions yet. Resolve an escalation to see invest, monitor, or pass outcomes." />
      </div>
    );
  }

  return (
    <div className="flex flex-col relative">
      {decisions.map((item, i) => (
        <RowWrapper key={item.id} index={i}>
          <div className="flex flex-col gap-phi-2 min-w-0">
            <span className="type-meta text-oxford/20 group-hover:text-oxford/40 transition-colors tabular-nums">
              {(i + 1).toString().padStart(2, '0')}
            </span>
            <div className="flex flex-col gap-phi-1">
              <span className="type-meta uppercase tracking-[0.12em] text-oxford/35">Decision</span>
              <span className="type-meta text-oxford/70">{item.decision}</span>
            </div>
          </div>

          <div className="flex min-w-0 flex-col gap-phi-2">
            <div className="flex items-center gap-phi-2">
              <span className="type-meta uppercase tracking-[0.12em] text-oxford/40">Startup</span>
              <span className="type-meta text-oxford/20">·</span>
              <span className="type-label-tab text-oxford/75 truncate">{item.name}</span>
            </div>
            {item.notes ? (
              <p className="type-note text-oxford/62 leading-relaxed max-w-2xl">
                {item.notes}
              </p>
            ) : (
              <p className="type-meta text-oxford/40">No notes provided</p>
            )}
          </div>

          <div className="flex min-w-0 flex-col items-start gap-phi-5 lg:items-end">
            <div className="flex flex-col items-start lg:items-end gap-phi-2">
              <span className="type-meta uppercase tracking-[0.12em] text-oxford/35">Resolved</span>
              <span className="font-mono type-meta text-oxford/50 tabular-nums">
                {item.resolvedAt ? new Date(item.resolvedAt).toLocaleDateString('en-GB') : '--'}
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
    <section className="flex flex-col gap-phi-3 px-phi-4 py-phi-4 border-b border-oxford/[0.06] last:border-0">
      <div className="flex items-center justify-between border-b border-oxford/[0.06] pb-phi-2">
        <h3 className="type-meta uppercase tracking-[0.12em] text-oxford/50">{title}</h3>
        {label && <span className="type-meta uppercase tracking-[0.12em] text-oxford/30">{label}</span>}
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
          <p className="type-meta text-oxford/45 uppercase tracking-[0.12em]">No rejection data yet</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-phi-5 gap-y-phi-4">
            {rejection.most_common_red_flags.slice(0, 6).map((rf, i) => (
              <div key={rf.flag} className="flex flex-col gap-phi-2">
                <div className="flex justify-between items-baseline">
                  <span className="type-meta text-oxford/40 uppercase tracking-[0.12em]">{rf.flag.replace(/_/g, ' ')}</span>
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
            <div key={s.label} className="flex flex-col gap-phi-1">
              <span className="font-mono font-bold text-[clamp(22px,2vw,30px)] leading-none tracking-[-0.04em] tabular-nums text-oxford">{s.value}</span>
              <span className="type-meta text-oxford/40 uppercase tracking-[0.1em]">{s.label}</span>
            </div>
          ))}
        </div>
      </TabSection>

      <TabSection title="Sector Concentration" label="Distribution">
        {sectors.length === 0 ? (
          <p className="type-meta text-oxford/45 uppercase tracking-[0.18em]">No concentration data yet</p>
        ) : (
          <div className="flex flex-col gap-phi-4">
            {sectors.map(([sector, data], i) => (
              <div key={sector} className="grid grid-cols-[100px_1fr_44px] gap-phi-4 items-center">
                <span className="type-meta text-oxford/60 uppercase tracking-[0.12em] truncate">{sector}</span>
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
    <div className="px-phi-4 py-phi-6">
      <p className="type-meta text-oxford/45 uppercase tracking-[0.12em]">Loading...</p>
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
            <div className="flex flex-col gap-phi-3">
              <span className="type-meta text-oxford/30 uppercase tracking-[0.12em]">Target Sectors</span>
              <div className="flex flex-wrap gap-phi-2 mt-phi-1">
                {sectors.map(s => <span key={s} className="type-meta border border-oxford/[0.08] px-phi-2 py-phi-1 text-oxford/55">{s}</span>)}
              </div>
            </div>
            <div className="flex flex-col gap-phi-3">
              <span className="type-meta text-oxford/30 uppercase tracking-[0.12em]">Stage Focus</span>
              <div className="flex flex-wrap gap-phi-2 mt-phi-1">
                {stages.map(s => <span key={s} className="type-meta border border-oxford/[0.08] px-phi-2 py-phi-1 text-oxford/55">{s}</span>)}
              </div>
            </div>
          </div>
          <div className="flex flex-col gap-phi-3 p-phi-4 bg-oxford/[0.02] border border-oxford/[0.06]">
            <span className="type-meta text-oxford/30 uppercase tracking-[0.12em]">Agent Directive</span>
            <p className="type-body text-oxford/60 leading-relaxed italic">
              Scouts are calibrated to prioritize {sectors[0] || 'core sector'} opportunities within {stages[0] || 'targeted stage'} cycles.
              Mandate mode: <span className="text-oxford/80">{data.thesis_mode === 'embedding' ? 'AI Enhanced' : 'Rule Based'}</span>.
            </p>
          </div>
        </div>
      </TabSection>

      <TabSection title="Alignment">
        <div className="grid grid-cols-3 gap-phi-4">
          <div className="border border-oxford/10 bg-oxford/[0.02] px-phi-3 py-2">
            <span className="block font-mono font-semibold text-2xl text-oxford tabular-nums">{data.alignment_stats?.pct_matching_thesis ?? '--'}%</span>
            <span className="type-meta text-oxford/50">Mandate match</span>
          </div>
          <div className="border border-oxford/10 bg-oxford/[0.02] px-phi-3 py-2">
            <span className="block font-mono font-semibold text-2xl text-oxford tabular-nums">{data.alignment_stats?.avg_alignment_score ?? '--'}</span>
            <span className="type-meta text-oxford/50">Mean alignment</span>
          </div>
          <div className="border border-oxford/10 bg-oxford/[0.02] px-phi-3 py-2">
            <span className="block font-mono font-semibold text-2xl text-oxford tabular-nums">{data.alignment_stats?.drift_vs_previous ?? '0.00'}</span>
            <span className="type-meta text-oxford/50">Drift</span>
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
              <div key={s.label} className="flex flex-col gap-phi-1">
                <span className="font-mono font-bold text-[clamp(18px,1.6vw,24px)] leading-none tracking-[-0.04em] tabular-nums text-oxford">{s.value}</span>
                <span className="type-meta text-oxford/40 uppercase tracking-[0.1em]">{s.label}</span>
              </div>
            ))}
          </div>
          {lastReport.no_action_reasons.length > 0 && (
            <div className="mt-phi-4 bg-oxford/[0.02] px-phi-4 py-phi-3">
              {lastReport.no_action_reasons.map((r, i) => (
                <p key={i} className="type-meta text-oxford/55 leading-relaxed">{r}</p>
              ))}
            </div>
          )}
        </TabSection>
      ) : (
        <TabSection title="Last Cycle">
          <p className="type-meta text-oxford/45 uppercase tracking-[0.18em]">No cycles run yet</p>
        </TabSection>
      )}
      <TabSection title="Scout Allocation" label="Weights">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-phi-5 gap-y-phi-4">
          {([
            ['Market Scout', weights.MarketDrivenScout],
            ['Technical Scout', weights.BuilderTechnicalScout],
            ['Pain Point Scout', weights.PainPointScout],
            ['Contrarian Scout', weights.ContrarianScout],
          ] as [string, number][]).map(([name, w], i) => (
            <div key={name} className="flex flex-col gap-phi-2">
              <div className="flex justify-between items-baseline">
                <span className="type-meta text-oxford/40 uppercase tracking-[0.12em]">{name}</span>
                <span className="font-mono type-meta text-oxford/60 tabular-nums">{Math.round(w * 100)}%</span>
              </div>
              <TacticalBar pct={w * 100} delay={i * 0.1} />
            </div>
          ))}
        </div>
      </TabSection>

      <TabSection title="Calibration Log">
        {calibration.calibration_history.length === 0 ? (
          <p className="type-meta text-oxford/45 uppercase tracking-[0.18em]">No calibration history yet</p>
        ) : (
          <div className="flex flex-col border border-oxford/[0.06] bg-oxford/[0.01]">
            {calibration.calibration_history.slice(-5).reverse().map((h, i) => (
              <div key={i} className="grid grid-cols-[100px_1fr] gap-phi-4 border-b border-oxford/[0.06] last:border-0 p-phi-4 items-start">
                <span className={`type-meta px-phi-2 py-phi-1 border ${h.direction === 'tightened' ? 'border-escalation/20 text-escalation/70' : 'border-oxford/[0.08] text-oxford/55'} text-center`}>
                  {h.direction}
                </span>
                <div className="flex flex-col gap-phi-2">
                  <span className="type-meta text-oxford/70 tracking-[0.06em]">{h.parameter.replace(/_/g, ' ')}</span>
                  <p className="type-meta text-oxford/45 leading-relaxed font-mono">{h.reasoning}</p>
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
      <div className="sticky top-0 z-20 bg-paper border-b border-oxford/[0.06] px-phi-4 py-phi-2">
        <div className="flex flex-wrap items-center justify-between gap-x-phi-4 gap-y-phi-2">
          <div className="flex min-w-0 flex-wrap items-center gap-phi-3">
            <span className={UI_FILTER_TOOLBAR_LABEL}>System</span>
            <div className="flex items-center gap-0">
              {TABS.map((tab) => {
                const isActive = activeTab === tab.key;
                return (
                  <FilterButton
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    active={isActive}
                    label={tab.label}
                  />
                );
              })}
            </div>
          </div>
          {props.onClose && (
            <button
              type="button"
              onClick={props.onClose}
              className="type-meta min-h-[36px] text-oxford/55 hover:text-oxford transition-colors pl-phi-2"
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
          {activeTab === 'decisions' && <DecisionsTab startups={props.startups} />}
          {activeTab === 'thesis' && <InstitutionalMandateTab />}
          {activeTab === 'meta' && (
            <MetaCommandTab reports={props.metaReports} weights={props.scoutWeights} calibration={props.calibrationState} />
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
