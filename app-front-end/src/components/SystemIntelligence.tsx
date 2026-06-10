import { useState, useEffect, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence, type Variants } from 'framer-motion';
import { tokens } from '../design-system/tokens';
import type {
  Startup, RejectionAnalytics, WatchlistAnalytics,
  ConcentrationAnalytics, MetaCycleReport, MetaPromptState, MetaEvalSet, PromptEvaluateResult, ScoutWeights, CalibrationState,
  HumanFeedbackSummary, SystemHealthSnapshot, MetaInsightsPayload,
  CalibrationChangeSummary, WeightUpdateSummary, PromptMutationSummary,
} from '../types/startup';
import type { FundThesisRuntime } from '../api/fundThesis';
import { triggerMetaCycle, promoteMetaPrompt, resetMetaPrompt, saveMetaEvalSet, runPromptEvaluation } from '../api/meta';
import { transitionOrReduced } from '../design-system/motion';
import { usePrefersReducedMotion } from '../hooks';
import EmptyState from './EmptyState';
import DecisionBadge, { DECISION_BADGE_LABEL, type DecisionBadgeVariant } from './DecisionBadge';
import { buildFundIntelligenceSnapshot } from '../lib/institutionalConviction';
import { createDefaultFundConfiguration, type FundConfiguration } from '../lib/fundConfiguration';

/**
 * The five facets of the instrument, ordered by how an investor reads it:
 * what it hunts (Mandate), what the human ruled (Record), what its decisions
 * show (Patterns), how tightly it is tuned (Calibration), how it rewrites
 * itself (Evolution). Signals live in Portfolio, where they act on conviction.
 */
type Tab = 'analytics' | 'decisions' | 'calibration' | 'thesis' | 'meta';
const TABS: { key: Tab; label: string }[] = [
  { key: 'thesis', label: 'Mandate' },
  { key: 'decisions', label: 'Record' },
  { key: 'analytics', label: 'Patterns' },
  { key: 'calibration', label: 'Calibration' },
  { key: 'meta', label: 'Evolution' },
];

interface SystemIntelligenceProps {
  startups: Startup[];
  onStartupClick?: (startup: Startup) => void;
  selectedStartupId?: string | null;
  rejectionAnalytics: RejectionAnalytics;
  watchlistAnalytics: WatchlistAnalytics;
  concentrationAnalytics: ConcentrationAnalytics;
  systemHealth: SystemHealthSnapshot | null;
  metaReports: MetaCycleReport[];
  scoutWeights: ScoutWeights;
  calibrationState: CalibrationState;
  metaPromptState: MetaPromptState;
  metaEvalSet: MetaEvalSet;
  metaInsights: MetaInsightsPayload | null;
  fundThesisRuntime: FundThesisRuntime | null;
  fundThesisRuntimeLoading?: boolean;
  fundThesisRuntimeError?: string | null;
  fundConfiguration?: FundConfiguration;
}

function mandateTagList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((x): x is string => typeof x === 'string' && x.trim().length > 0);
}

function formatAlignmentPct(score: number | null | undefined): string {
  if (score == null || Number.isNaN(score)) return '--';
  return `${Math.round(score * 100)}%`;
}

function formatDrift(drift: number | null | undefined): string {
  if (drift == null || Number.isNaN(drift)) return '--';
  const rounded = Math.round(drift * 1000) / 1000;
  return rounded > 0 ? `+${rounded.toFixed(2)}` : rounded.toFixed(2);
}

const REVIEWER_EVAL_AGENTS = new Set(['DefaultReviewer', 'SkepticalReviewer', 'OpportunistReviewer']);

const TAB_CONTENT_CONTAINER_VARIANTS: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.05, delayChildren: 0.03 } },
};

const TAB_CONTENT_ITEM_VARIANTS: Variants = {
  hidden: { opacity: 0, transform: 'translateY(8px)' },
  visible: {
    opacity: 1,
    transform: 'translateY(0px)',
    transition: { duration: 0.35, ease: tokens.motion.ease },
  },
};

function AnimatedTabBlock({
  children,
  className = '',
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const reduceMotion = usePrefersReducedMotion();
  if (reduceMotion) {
    return className ? <div className={className}>{children}</div> : <>{children}</>;
  }
  return (
    <motion.div variants={TAB_CONTENT_ITEM_VARIANTS} className={className || undefined}>
      {children}
    </motion.div>
  );
}

const FilterButton = ({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) => (
  <button
    type="button"
    onClick={onClick}
    className={`type-meta uppercase tracking-[0.12em] min-h-[36px] px-phi-3 transition-colors btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 ${active ? 'text-oxford font-semibold' : 'text-oxford/40 hover:text-oxford/70'
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
function RowWrapper({
  children,
  index,
  onClick,
  isSelected,
  ariaLabel,
}: {
  children: React.ReactNode;
  index: number;
  onClick?: () => void;
  isSelected?: boolean;
  ariaLabel?: string;
}) {
  const reduceMotion = usePrefersReducedMotion();
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!onClick) return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick();
    }
  };
  return (
    <motion.div
      initial={reduceMotion ? {} : { opacity: 0, transform: 'translateY(6px)' }}
      animate={{ opacity: 1, transform: 'translateY(0px)' }}
      transition={{ delay: Math.min(index * 0.03, 0.3), duration: 0.4, ease: tokens.motion.ease }}
      className={`group relative py-phi-3 px-phi-4 transition-colors duration-200 ease-smooth focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 ${onClick ? 'cursor-pointer' : ''
        } ${isSelected ? 'bg-surface-selected' : 'hover:bg-registerTint'}`}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      aria-pressed={onClick ? isSelected : undefined}
      aria-label={onClick ? ariaLabel : undefined}
      onClick={onClick}
      onKeyDown={handleKeyDown}
    >
      <div className="grid grid-cols-1 gap-phi-3 items-start lg:grid-cols-[26px_minmax(0,1fr)_auto]">
        {children}
      </div>
    </motion.div>
  );
}

function humanResolutionBadgeVariant(decision: 'YES' | 'NO' | 'MAYBE'): DecisionBadgeVariant {
  if (decision === 'YES') return 'INVEST';
  if (decision === 'MAYBE') return 'MONITOR';
  return 'PASS';
}

/* ─── DECISIONS ─── */
function DecisionsTab({
  startups,
  onStartupClick,
  selectedStartupId,
}: {
  startups: Startup[];
  onStartupClick?: (startup: Startup) => void;
  selectedStartupId?: string | null;
}) {
  const decisions = startups
    .filter((startup) => startup.human_resolution?.decision)
    .map((startup) => {
      const raw = startup.human_resolution!.decision as 'YES' | 'NO' | 'MAYBE';
      return {
        startup,
        id: startup.id,
        name: startup.scout?.name?.trim() || startup.id,
        badgeVariant: humanResolutionBadgeVariant(raw),
        notes: startup.human_resolution?.notes?.trim() ?? '',
        resolvedAt: startup.human_resolution?.resolved_at,
      };
    })
    .sort((a, b) => {
      const ta = a.resolvedAt ? new Date(a.resolvedAt).getTime() : 0;
      const tb = b.resolvedAt ? new Date(b.resolvedAt).getTime() : 0;
      return tb - ta;
    });

  if (decisions.length === 0) {
    return (
      <AnimatedTabBlock className="py-phi-6 px-phi-4 flex items-center justify-center">
        <EmptyState
          label="Human resolutions"
          body="No escalation resolutions yet. When you resolve a human review from the deal grid, the outcome and notes appear here. Partner verdicts stay on each deal row."
        />
      </AnimatedTabBlock>
    );
  }

  return (
    <AnimatedTabBlock className="flex flex-col relative divide-y divide-oxford/[0.06]">
      {decisions.map((item, i) => {
        const resolvedLabel = item.resolvedAt
          ? new Date(item.resolvedAt).toLocaleDateString('en-GB')
          : 'date unknown';
        return (
        <RowWrapper
          key={item.id}
          index={i}
          onClick={onStartupClick ? () => onStartupClick(item.startup) : undefined}
          isSelected={selectedStartupId === item.id}
          ariaLabel={`Open memo for ${item.name}, ${DECISION_BADGE_LABEL[item.badgeVariant]}, resolved ${resolvedLabel}`}
        >
          <span className="font-mono type-meta text-oxford/20 group-hover:text-oxford/40 transition-colors tabular-nums pt-px">
            {(i + 1).toString().padStart(2, '0')}
          </span>

          <div className="flex min-w-0 flex-col gap-phi-2">
            <div className="flex flex-wrap items-center gap-x-phi-3 gap-y-phi-2">
              <span className="type-label-tab text-oxford/80 truncate">{item.name}</span>
              <DecisionBadge variant={item.badgeVariant} />
            </div>
            {item.notes ? (
              <p className="type-note text-oxford/60 leading-relaxed max-w-2xl">
                {item.notes}
              </p>
            ) : (
              <p className="type-meta text-oxford/40">No notes</p>
            )}
          </div>

          <div className="min-w-0 lg:text-right shrink-0">
            <span className="font-mono type-meta text-oxford/45 tabular-nums">
              {item.resolvedAt ? new Date(item.resolvedAt).toLocaleDateString('en-GB') : '—'}
            </span>
          </div>
        </RowWrapper>
        );
      })}
    </AnimatedTabBlock>
  );
}

function CalibrationTab({ startups, fundConfiguration }: { startups: Startup[]; fundConfiguration?: FundConfiguration }) {
  const config = fundConfiguration ?? createDefaultFundConfiguration();
  const snapshot = buildFundIntelligenceSnapshot(startups, config);
  const hasDecisions = Object.values(snapshot.decisionsByOutcome).some((count) => count > 0);

  if (!startups.length || !hasDecisions) {
    return (
      <AnimatedTabBlock className="py-phi-6 px-phi-4 flex items-center justify-center">
        <EmptyState
          label="Calibration"
          body="Calibration will emerge as decisions accumulate."
        />
      </AnimatedTabBlock>
    );
  }

  return (
    <>
      <TabSection title="Fund Intelligence" label="Derived">
        <div className="flex flex-wrap gap-phi-6">
          {snapshot.observations.map((item) => (
            <div key={item.label} className="flex flex-col gap-phi-1">
              <span className="font-mono font-semibold text-[clamp(22px,2vw,30px)] leading-none tracking-0 tabular-nums text-oxford">{item.value}</span>
              <span className="type-meta text-oxford/40 uppercase tracking-[0.1em]">{item.label}</span>
              {item.detail ? <span className="type-meta text-oxford/30">{item.detail}</span> : null}
            </div>
          ))}
        </div>
      </TabSection>
      <TabSection title="Decision Outcomes" label="Ledger">
        <div className="grid grid-cols-3 gap-phi-4 max-w-xl">
          {[
            ['Invest', snapshot.decisionsByOutcome.YES],
            ['Monitor', snapshot.decisionsByOutcome.MAYBE],
            ['Pass', snapshot.decisionsByOutcome.NO],
          ].map(([label, value]) => (
            <div key={label} className="border-t border-oxford/[0.08] pt-phi-3">
              <span className="font-mono type-meta text-oxford/65 tabular-nums">{value}</span>
              <span className="block mt-phi-1 type-meta uppercase tracking-[0.12em] text-oxford/38">{label}</span>
            </div>
          ))}
        </div>
      </TabSection>
      <TabSection title="Recurring Risk Themes" label="Observed">
        {snapshot.commonRiskThemes.length ? (
          <ul className="flex flex-col">
            {snapshot.commonRiskThemes.map((item) => (
              <li key={item.theme} className="flex items-baseline justify-between gap-phi-4 border-t border-oxford/[0.06] py-phi-3 first:border-t-0">
                <span className="type-note text-oxford/68">{item.theme}</span>
                <span className="font-mono type-meta text-oxford/45 tabular-nums">{item.count}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="type-note text-oxford/50 leading-relaxed max-w-xl">
            No recurring risk themes are extractable from the current resolved set.
          </p>
        )}
      </TabSection>
    </>
  );
}

/* ─── SECTION WRAPPER ─── */
function TabSection({ title, label, children }: { title: string; label?: string; children: React.ReactNode }) {
  const reduceMotion = usePrefersReducedMotion();
  const header = (
    <div className="flex flex-wrap items-baseline justify-between gap-x-phi-4 gap-y-phi-1">
      <h3 className="type-meta uppercase tracking-[0.12em] text-oxford/50">{title}</h3>
      {label ? <span className="type-meta uppercase tracking-[0.12em] text-oxford/30">{label}</span> : null}
    </div>
  );

  if (reduceMotion) {
    return (
      <section className="flex flex-col gap-phi-3 px-phi-4 pt-phi-5 pb-phi-5 first:pt-phi-3">
        {header}
        {children}
      </section>
    );
  }

  return (
    <motion.section
      variants={TAB_CONTENT_ITEM_VARIANTS}
      className="flex flex-col gap-phi-3 px-phi-4 pt-phi-5 pb-phi-5 first:pt-phi-3"
    >
      {header}
      {children}
    </motion.section>
  );
}

/* ─── ANALYTICS ─── */
function AnalyticsTab({ rejection, watchlist, concentration, systemHealth }: {
  rejection: RejectionAnalytics; watchlist: WatchlistAnalytics; concentration: ConcentrationAnalytics;
  systemHealth: SystemHealthSnapshot | null;
}) {
  const maxRedFlag = Math.max(...rejection.most_common_red_flags.map((r) => r.count), 1);
  const sectors = Object.entries(concentration.by_sector).sort((a, b) => b[1].count - a[1].count).slice(0, 8);
  const maxSector = Math.max(...sectors.map(([, v]) => v.count), 1);
  const q = systemHealth?.queue_depths;

  return (
    <>
      {systemHealth && (
        <TabSection title="Pipeline health" label="Live">
          <div className="flex flex-wrap gap-phi-6">
            {[
              { label: 'Awaiting review', value: q?.unreviewed ?? 0 },
              { label: 'Awaiting partner', value: q?.undecided ?? 0 },
              { label: 'Watchlist', value: q?.watchlist ?? 0 },
              { label: 'Escalations', value: systemHealth.pending_escalations },
            ].map((s) => (
              <div key={s.label} className="flex flex-col gap-phi-1">
                <span className="font-mono font-semibold text-[clamp(22px,2vw,30px)] leading-none tracking-[-0.03em] tabular-nums text-oxford">{s.value}</span>
                <span className="type-meta text-oxford/40 uppercase tracking-[0.1em]">{s.label}</span>
              </div>
            ))}
          </div>
          {systemHealth.calibration_warning ? (
            <p className="type-meta text-oxford/55 leading-relaxed mt-phi-6 max-w-2xl pt-phi-2">
              Calibration note: {systemHealth.calibration_warning}
            </p>
          ) : null}
        </TabSection>
      )}
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
              <span className="font-mono font-semibold text-[clamp(22px,2vw,30px)] leading-none tracking-[-0.03em] tabular-nums text-oxford">{s.value}</span>
              <span className="type-meta text-oxford/40 uppercase tracking-[0.1em]">{s.label}</span>
            </div>
          ))}
        </div>
        {watchlist.entries && watchlist.entries.length > 0 && (
          <div className="mt-phi-6 flex flex-col gap-phi-3 pt-phi-2">
            <span className="type-meta uppercase tracking-[0.12em] text-oxford/35">Companies</span>
            <ul className="flex flex-col">
              {watchlist.entries.slice(0, 10).map((e, i) => (
                <li key={e.startup_id ?? `wl-${i}`} className="flex flex-wrap items-baseline justify-between gap-x-phi-4 gap-y-phi-1 py-phi-3 first:pt-0">
                  <span className="type-note text-oxford/70 truncate min-w-0 max-w-[min(100%,20rem)]">
                    {e.startup_name?.trim() || e.startup_id?.slice(0, 8) || 'Unknown'}
                  </span>
                  <span className="font-mono type-meta text-oxford/45 tabular-nums shrink-0">
                    {e.days_on_watchlist != null ? `${e.days_on_watchlist}d` : '—'}
                    {e.stale_warning ? ' · stale' : ''}
                    {e.signal_count != null && e.signal_count > 0 ? ` · ${e.signal_count} sig` : ''}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </TabSection>

      <TabSection title="Sector Concentration" label="Distribution">
        {sectors.length === 0 ? (
          <div className="flex flex-col gap-phi-2">
            <p className="type-meta text-oxford/45 uppercase tracking-[0.18em]">No concentration data yet</p>
            <p className="type-note text-oxford/50 leading-relaxed max-w-xl">
              Distribution refreshes when the pipeline runs portfolio health and cluster analysis over your deal set.
            </p>
          </div>
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
    </>
  );
}

function MandateTagGroup({ label, tags }: { label: string; tags: string[] }) {
  return (
    <div className="flex flex-col gap-phi-3">
      <span className="type-meta text-oxford/30 uppercase tracking-[0.12em]">{label}</span>
      {tags.length > 0 ? (
        <div className="flex flex-wrap gap-phi-2 mt-phi-1">
          {tags.map((s) => (
            <span key={s} className="type-meta bg-registerTint px-phi-2 py-phi-1 text-oxford/55">{s}</span>
          ))}
        </div>
      ) : (
        <p className="type-meta text-oxford/40">Not specified</p>
      )}
    </div>
  );
}

/* ─── FUND THESIS ─── */
function InstitutionalMandateTab({
  data,
  loading,
  error,
}: {
  data: FundThesisRuntime | null;
  loading?: boolean;
  error?: string | null;
}) {
  if (error) {
    return (
      <AnimatedTabBlock className="py-phi-6 px-phi-4 flex items-center justify-center">
        <EmptyState label="Fund Thesis" body="Could not load thesis data. Check your API connection and try again." />
      </AnimatedTabBlock>
    );
  }

  if (loading && !data) {
    return (
      <AnimatedTabBlock className="px-phi-4 py-phi-4">
        <p className="type-meta text-oxford/45 uppercase tracking-[0.12em]">Loading...</p>
      </AnimatedTabBlock>
    );
  }

  if (!data || data.mode === 'missing' || (!data.parsed_json && data.thesis_ready === false)) {
    return (
      <AnimatedTabBlock className="py-phi-6 px-phi-4 flex items-center justify-center">
        <EmptyState label="Fund Thesis" body="No active thesis configured. Set up your investment mandate in Settings to enable thesis-aligned scouting." />
      </AnimatedTabBlock>
    );
  }

  const pj = data.parsed_json ?? {};
  const sectors = mandateTagList(pj.sectors);
  const stages = mandateTagList(pj.stage_focus);
  const reviewedCount = data.alignment_stats?.reviewed_with_thesis_count ?? 0;
  const pctMatch = data.alignment_stats?.pct_matching_thesis;
  const mandateMode = data.thesis_mode === 'embedding' ? 'AI Enhanced' : 'Rule Based';

  return (
    <>
      <TabSection title="Portfolio Mandate" label={`v${data.active_version_number ?? '01'}`}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-phi-5">
          <div className="flex flex-col gap-phi-5">
            <MandateTagGroup label="Target Sectors" tags={sectors} />
            <MandateTagGroup label="Stage Focus" tags={stages} />
          </div>
          <div className="flex flex-col gap-phi-3 p-phi-4 bg-registerTint">
            <span className="type-meta text-oxford/30 uppercase tracking-[0.12em]">Agent Directive</span>
            <p className="type-body text-oxford/60 leading-relaxed italic">
              Scouts prioritize {sectors[0] || 'core sector'} at {stages[0] || 'target stage'}.
              {' '}
              <span className="text-oxford/80">{mandateMode}</span> mandate.
            </p>
          </div>
        </div>
      </TabSection>

      <TabSection title="Alignment" label={reviewedCount > 0 ? `${reviewedCount} reviewed` : undefined}>
        <div className="grid grid-cols-3 gap-phi-4">
          <div className="bg-registerTint px-phi-3 py-phi-3">
            <span className="block font-mono font-semibold text-2xl text-oxford tabular-nums">
              {pctMatch != null ? `${pctMatch}%` : '--'}
            </span>
            <span className="type-meta text-oxford/50">Mandate match</span>
          </div>
          <div className="bg-registerTint px-phi-3 py-phi-3">
            <span className="block font-mono font-semibold text-2xl text-oxford tabular-nums">
              {formatAlignmentPct(data.alignment_stats?.avg_alignment_score)}
            </span>
            <span className="type-meta text-oxford/50">Mean alignment</span>
          </div>
          <div className="bg-registerTint px-phi-3 py-phi-3">
            <span className="block font-mono font-semibold text-2xl text-oxford tabular-nums">
              {formatDrift(data.alignment_stats?.drift_vs_previous)}
            </span>
            <span className="type-meta text-oxford/50">Drift</span>
          </div>
        </div>
      </TabSection>

      {(data.version_timeline?.length ?? 0) > 0 && (
        <TabSection title="Version History">
          <ul className="flex flex-col border border-oxford/[0.06] bg-oxford/[0.01] divide-y divide-oxford/[0.06]">
            {(data.version_timeline ?? []).slice(0, 5).map((v) => (
              <li key={v.id} className="flex flex-wrap items-baseline justify-between gap-phi-3 px-phi-4 py-phi-3">
                <span className="type-meta text-oxford/65">
                  v{v.version_number}
                  {v.is_active ? ' · active' : ''}
                </span>
                <span className="font-mono type-meta text-oxford/40 tabular-nums">
                  {v.created_at ? new Date(v.created_at).toLocaleDateString('en-GB') : '—'}
                </span>
              </li>
            ))}
          </ul>
        </TabSection>
      )}
    </>
  );
}

/* ─── META AGENT ─── */
function MetaCommandTab({ reports, weights, calibration, promptState, metaEvalSet, insights }: {
  reports: MetaCycleReport[];
  weights: ScoutWeights;
  calibration: CalibrationState;
  promptState: MetaPromptState;
  metaEvalSet: MetaEvalSet;
  insights: MetaInsightsPayload | null;
}) {
  const queryClient = useQueryClient();
  const [triggering, setTriggering] = useState(false);
  const [promptBusy, setPromptBusy] = useState<string | null>(null);
  const [evalBusy, setEvalBusy] = useState<string | null>(null);
  const [evalDraft, setEvalDraft] = useState(() => metaEvalSet.startup_ids.join('\n'));
  const [evalSaveNote, setEvalSaveNote] = useState<string | null>(null);
  const [evalResult, setEvalResult] = useState<PromptEvaluateResult | null>(null);

  const evalSetSig = metaEvalSet.startup_ids.join('|');
  useEffect(() => {
    setEvalDraft(metaEvalSet.startup_ids.join('\n'));
  }, [evalSetSig]);
  const invalidateMeta = () => {
    void queryClient.invalidateQueries({ queryKey: ['meta'] });
  };
  const handleTrigger = async () => {
    setTriggering(true);
    try {
      await triggerMetaCycle();
      invalidateMeta();
    } finally {
      setTriggering(false);
    }
  };

  const lastReport = reports.length > 0 ? reports[0] : null;
  const proposalCount = Math.max(
    lastReport?.prompt_proposals?.length ?? 0,
    lastReport?.mutations_applied?.length ?? 0,
  );
  const calibrationCount = lastReport?.calibration_changes?.length ?? 0;

  const agentFromLibraryKey = (libraryKey: string) => libraryKey.split(':')[0] ?? '';

  const humanFb: HumanFeedbackSummary | undefined =
    lastReport?.signal_summary?.human_feedback ?? insights?.signal_summary?.human_feedback;
  const humanFbLine =
    humanFb && humanFb.recent_count > 0
      ? `Recorded ${humanFb.recent_count} analyst confirmations in the last correction signal (Invest ${humanFb.by_outcome?.YES ?? 0}, Pass ${humanFb.by_outcome?.NO ?? 0}, Monitor ${humanFb.by_outcome?.MAYBE ?? 0}${humanFb.disagreed_with_ai_count ? `; ${humanFb.disagreed_with_ai_count} differed from the AI recommendation at resolve time` : ''}).`
      : null;

  const wc = insights?.what_changed;
  const insightPromptCount = Math.max(wc?.mutations_applied?.length ?? 0, wc?.prompt_proposals?.length ?? 0);
  const insightWeightCount = wc?.weight_updates?.length ?? 0;
  const insightCalibrationCount = wc?.calibration_changes?.length ?? 0;
  const whatChangedTotal = insightPromptCount + insightWeightCount + insightCalibrationCount;
  const insightMutations = (
    (wc?.mutations_applied?.length ? wc.mutations_applied : wc?.prompt_proposals) ?? []
  ) as PromptMutationSummary[];
  const insightWeights = (wc?.weight_updates ?? []) as WeightUpdateSummary[];
  const insightCalibrations = (wc?.calibration_changes ?? []) as CalibrationChangeSummary[];
  const showLatestInsight =
    !!insights?.latest && ((insights?.why?.length ?? 0) > 0 || whatChangedTotal > 0);

  return (
    <>
      <AnimatedTabBlock className="px-phi-4 pt-phi-4 pb-phi-5 border-b border-oxford/[0.06]">
        <p className="type-body text-oxford/65 leading-relaxed max-w-2xl">
          This tab runs the scheduled correction cycle: it proposes updates to scouts, reviewers, and score thresholds.
          When you confirm <span className="text-oxford/80">Invest</span>, <span className="text-oxford/80">Pass</span>, or{' '}
          <span className="text-oxford/80">Monitor</span> in the deal grid with a short rationale, that is saved and folded into the next cycle so the system drifts toward how you actually decide—not generic defaults.
        </p>
        {humanFbLine && (
          <p className="type-meta text-oxford/45 leading-relaxed max-w-2xl mt-phi-3">{humanFbLine}</p>
        )}
      </AnimatedTabBlock>
      {showLatestInsight && insights?.latest && (
        <TabSection
          title="Latest insight"
          label={insights.latest.ran_at ? new Date(insights.latest.ran_at).toLocaleDateString('en-GB') : undefined}
        >
          <div className="flex flex-wrap gap-phi-6 mb-phi-3">
            {typeof insights.latest.cycle_number === 'number' && (
              <div className="flex flex-col gap-phi-1">
                <span className="font-mono font-semibold text-xl tabular-nums text-oxford">{insights.latest.cycle_number}</span>
                <span className="type-meta text-oxford/40 uppercase tracking-[0.1em]">Cycle</span>
              </div>
            )}
            {whatChangedTotal > 0 && (
              <>
                {insightPromptCount > 0 && (
                  <div className="flex flex-col gap-phi-1">
                    <span className="font-mono font-semibold text-xl tabular-nums text-oxford">{insightPromptCount}</span>
                    <span className="type-meta text-oxford/40 uppercase tracking-[0.1em]">Prompts</span>
                  </div>
                )}
                {insightWeightCount > 0 && (
                  <div className="flex flex-col gap-phi-1">
                    <span className="font-mono font-semibold text-xl tabular-nums text-oxford">{insightWeightCount}</span>
                    <span className="type-meta text-oxford/40 uppercase tracking-[0.1em]">Weights</span>
                  </div>
                )}
                {insightCalibrationCount > 0 && (
                  <div className="flex flex-col gap-phi-1">
                    <span className="font-mono font-semibold text-xl tabular-nums text-oxford">{insightCalibrationCount}</span>
                    <span className="type-meta text-oxford/40 uppercase tracking-[0.1em]">Calibration</span>
                  </div>
                )}
              </>
            )}
          </div>
          {whatChangedTotal > 0 && (
            <div className="flex flex-col gap-phi-3 mb-phi-4 border border-oxford/[0.06] bg-oxford/[0.01] divide-y divide-oxford/[0.06]">
              {insightMutations.map((m, i) => (
                <p key={`mut-${m.agent_target}-${i}`} className="type-meta text-oxford/55 leading-relaxed px-phi-4 py-phi-3">
                  <span className="text-oxford/70">{m.agent_target}</span>
                  {m.reasoning ? ` — ${m.reasoning}` : ''}
                </p>
              ))}
              {insightWeights.map((w, i) => (
                <p key={`wt-${w.agent_target}-${i}`} className="type-meta text-oxford/55 leading-relaxed px-phi-4 py-phi-3 font-mono">
                  {w.agent_target}: {Math.round((w.previous_weight ?? 0) * 100)}% → {Math.round((w.new_weight ?? 0) * 100)}%
                </p>
              ))}
              {insightCalibrations.map((c, i) => (
                <p key={`cal-${c.parameter}-${i}`} className="type-meta text-oxford/55 leading-relaxed px-phi-4 py-phi-3">
                  <span className="text-oxford/70">{c.parameter.replace(/_/g, ' ')}</span>
                  {c.direction ? ` (${c.direction})` : ''}
                  {c.reasoning ? ` — ${c.reasoning}` : ''}
                </p>
              ))}
            </div>
          )}
          {(insights?.why?.length ?? 0) > 0 && (
            <div className="flex flex-col gap-phi-2">
              <span className="type-meta text-oxford/35 uppercase tracking-[0.12em]">Why (no-action / guardrails)</span>
              {(insights?.why ?? []).map((line, i) => (
                <p key={i} className="type-meta text-oxford/55 leading-relaxed">{line}</p>
              ))}
            </div>
          )}
        </TabSection>
      )}
      {lastReport ? (
        <TabSection title="Last Cycle" label={`Cycle ${lastReport.cycle_number}`}>
          <div className="flex flex-wrap gap-phi-6">
            {[
              { label: 'Ran', value: new Date(lastReport.ran_at).toLocaleDateString('en-GB') },
              { label: 'Prompt proposals', value: proposalCount },
              { label: 'Weight updates', value: (lastReport.weight_updates ?? []).length },
              { label: 'Calibration', value: calibrationCount },
            ].map((s) => (
              <div key={s.label} className="flex flex-col gap-phi-1">
                <span className="font-mono font-semibold text-[clamp(18px,1.6vw,24px)] leading-none tracking-[-0.03em] tabular-nums text-oxford">{s.value}</span>
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

      <AnimatedTabBlock>
      <details className="group border-b border-oxford/[0.06]">
        <summary className="cursor-pointer list-none px-phi-4 py-phi-4 type-meta uppercase tracking-[0.12em] text-oxford/45 hover:text-oxford/70 marker:content-none flex items-center justify-between gap-phi-3">
          <span>Advanced — prompt checks (optional)</span>
          <span className="type-meta text-oxford/25 group-open:hidden">Show</span>
          <span className="type-meta text-oxford/25 hidden group-open:inline">Hide</span>
        </summary>
        <div className="flex flex-col pb-phi-2">
        <p className="type-body text-oxford/55 leading-relaxed px-phi-4 pt-phi-3 max-w-2xl">
          You can ignore this unless the correction cycle has produced <span className="text-oxford/75">pending prompt drafts</span> and you want to test or turn them on.
          Day-to-day deal work and your Invest / Pass / Monitor confirmations do not depend on anything here—the product runs on built-in prompts until you explicitly promote a draft.
        </p>
      <TabSection title="Bench list" label="For Evaluate only">
        <p className="type-meta text-oxford/50 leading-relaxed mb-phi-3 max-w-2xl">
          Paste internal startup IDs from your pipeline (one per line, up to {metaEvalSet.max}). When you press <span className="text-oxford/65">Evaluate</span> on a pending <em>reviewer</em> prompt, the system re-runs that reviewer on these deals with the proposed instructions and compares to saved scores—cheap guardrail before going live. Each ID is one extra model call.
        </p>
        <textarea
          value={evalDraft}
          onChange={(e) => setEvalDraft(e.target.value)}
          rows={5}
          className="w-full max-w-2xl font-mono type-meta text-oxford/70 bg-oxford/[0.03] border border-oxford/[0.1] px-phi-3 py-phi-2 resize-y"
          placeholder={'startup_id_one\nstartup_id_two'}
        />
        <div className="flex flex-wrap items-center gap-phi-3 mt-phi-3">
          <button
            type="button"
            disabled={promptBusy !== null || evalBusy !== null}
            onClick={async () => {
              const lines = evalDraft.split(/[\n,]+/).map((s) => s.trim()).filter(Boolean);
              setEvalSaveNote(null);
              try {
                const res = await saveMetaEvalSet(lines);
                invalidateMeta();
                const miss = res.missing_startup_ids?.length
                  ? ` Not found: ${res.missing_startup_ids.slice(0, 5).join(', ')}${(res.missing_startup_ids.length > 5) ? '…' : ''}.`
                  : '';
                setEvalSaveNote(`Saved ${res.startup_ids?.length ?? 0} ids.${miss}`);
              } catch (e) {
                console.error(e);
                setEvalSaveNote(e instanceof Error ? e.message : 'Save failed');
              }
            }}
            className="type-meta border border-oxford/15 px-phi-4 py-phi-2 text-oxford/55 hover:text-oxford hover:border-oxford/40 btn-interaction"
          >
            Save bench list
          </button>
          <span className="type-meta text-oxford/35">Saved: {metaEvalSet.count}</span>
        </div>
        {evalSaveNote && <p className="type-meta text-oxford/50 mt-phi-2">{evalSaveNote}</p>}
      </TabSection>

      <TabSection title="Prompt drafts" label="Active vs pending">
        <p className="type-meta text-oxford/50 leading-relaxed mb-phi-3 max-w-2xl">
          The meta cycle can propose new instructions for scouts/reviewers. <span className="text-oxford/65">Active</span> is what runs today (empty = product defaults).
          <span className="text-oxford/65"> Pending</span> is queued proposals—use <span className="text-oxford/65">Promote</span> to make one live, or <span className="text-oxford/65">Reset</span> to drop back to defaults.
          Your org may require a passing <span className="text-oxford/65">Evaluate</span> before Promote for reviewers.
        </p>
        {promptState.restart_note && (
          <p className="type-meta text-oxford/50 leading-relaxed mb-phi-3 max-w-2xl">{promptState.restart_note}</p>
        )}
        <div className="flex flex-col gap-phi-4">
          <div>
            <span className="type-meta text-oxford/35 uppercase tracking-[0.12em] block mb-phi-2">Active (live)</span>
            {Object.keys(promptState.active).length === 0 ? (
              <p className="type-meta text-oxford/45">None—using built-in prompts.</p>
            ) : (
              <div className="flex flex-col border border-oxford/[0.06] bg-oxford/[0.01] divide-y divide-oxford/[0.06]">
                {Object.entries(promptState.active).map(([agent, libKey]) => (
                  <div key={agent} className="flex flex-wrap items-center justify-between gap-phi-3 p-phi-3">
                    <div className="min-w-0">
                      <span className="type-meta text-oxford/70">{agent}</span>
                      <p className="font-mono type-meta text-oxford/45 truncate max-w-xl" title={libKey}>{libKey}</p>
                    </div>
                    <button
                      type="button"
                      disabled={promptBusy !== null}
                      onClick={async () => {
                        setPromptBusy(agent);
                        try {
                          await resetMetaPrompt(agent);
                          invalidateMeta();
                        } catch (e) {
                          console.error(e);
                        } finally {
                          setPromptBusy(null);
                        }
                      }}
                      className="type-meta border border-oxford/15 px-phi-3 py-phi-2 text-oxford/50 hover:text-oxford hover:border-oxford/40 btn-interaction shrink-0"
                    >
                      {promptBusy === agent ? '…' : 'Use built-in default'}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div>
            <span className="type-meta text-oxford/35 uppercase tracking-[0.12em] block mb-phi-2">Pending (not live yet)</span>
            {promptState.pending.length === 0 ? (
              <p className="type-meta text-oxford/45">Nothing queued—defaults or only active prompts.</p>
            ) : (
              <div className="flex flex-col border border-oxford/[0.06] bg-oxford/[0.01] divide-y divide-oxford/[0.06] max-h-[280px] overflow-y-auto">
                {promptState.pending.map((p) => {
                  const agent = agentFromLibraryKey(p.library_key);
                  const canEval = REVIEWER_EVAL_AGENTS.has(agent);
                  return (
                    <div key={p.library_key} className="flex flex-wrap items-start justify-between gap-phi-3 p-phi-3">
                      <div className="min-w-0 flex-1">
                        <span className="type-meta text-oxford/70">{agent}</span>
                        <p className="font-mono type-meta text-oxford/45 break-all">{p.library_key}</p>
                        {p.reasoning && (
                          <p className="type-meta text-oxford/40 mt-phi-1 line-clamp-2">{p.reasoning}</p>
                        )}
                        <p className="type-meta text-oxford/30 mt-phi-1">
                          {p.prompt_char_count != null ? `${p.prompt_char_count} chars` : ''}
                          {p.created_at ? ` · ${new Date(p.created_at).toLocaleString('en-GB')}` : ''}
                        </p>
                      </div>
                      <div className="flex flex-col gap-phi-2 shrink-0">
                        {canEval && (
                          <button
                            type="button"
                            disabled={promptBusy !== null || evalBusy !== null}
                            onClick={async () => {
                              setEvalBusy(p.library_key);
                              setEvalResult(null);
                              try {
                                const r = await runPromptEvaluation(agent, p.library_key);
                                setEvalResult(r);
                                invalidateMeta();
                              } catch (e) {
                                console.error(e);
                                setEvalResult({ ok: false, error: e instanceof Error ? e.message : 'Eval failed' });
                              } finally {
                                setEvalBusy(null);
                              }
                            }}
                            className="type-meta border border-oxford/15 px-phi-3 py-phi-2 text-oxford/50 hover:text-oxford hover:border-oxford/40 btn-interaction"
                          >
                            {evalBusy === p.library_key ? '…' : 'Evaluate'}
                          </button>
                        )}
                        <button
                          type="button"
                          disabled={promptBusy !== null || evalBusy !== null}
                          onClick={async () => {
                            setPromptBusy(p.library_key);
                            try {
                              await promoteMetaPrompt(agent, p.library_key);
                              invalidateMeta();
                            } catch (e) {
                              console.error(e);
                            } finally {
                              setPromptBusy(null);
                            }
                          }}
                          className="type-meta border border-oxford/15 px-phi-3 py-phi-2 text-oxford/50 hover:text-oxford hover:border-oxford/40 btn-interaction"
                        >
                          {promptBusy === p.library_key ? '…' : 'Promote'}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
        {evalResult && (
          <div className="mt-phi-4 border border-oxford/[0.08] bg-oxford/[0.02] px-phi-4 py-phi-3 max-w-3xl">
            <span className="type-meta uppercase tracking-[0.12em] text-oxford/40 block mb-phi-2">Last evaluation</span>
            {!evalResult.ok && evalResult.error && (
              <p className="type-meta text-oxford/60">{evalResult.error}</p>
            )}
            {evalResult.summary && (
              <div className="flex flex-col gap-phi-2 type-meta text-oxford/65">
                <p>
                  <span className={evalResult.summary.passed ? 'text-oxford' : 'text-escalation/80'}>
                    {evalResult.summary.passed ? 'Passed' : 'Failed'}
                  </span>
                  {' · '}
                  {evalResult.summary.pass_reason}
                  {' · '}
                  regressions {evalResult.summary.regression_count} / {evalResult.summary.n_compared} compared
                  {' · '}
                  mean |Δscore| {evalResult.summary.mean_abs_score_delta}
                </p>
                {evalResult.truncated && (
                  <p className="text-oxford/45">Truncated to {evalResult.max_startups} startups.</p>
                )}
              </div>
            )}
            {evalResult.rows && evalResult.rows.length > 0 && (
              <details className="mt-phi-3">
                <summary className="type-meta text-oxford/50 cursor-pointer">Per startup</summary>
                <ul className="mt-phi-2 space-y-phi-1 font-mono type-meta text-oxford/45 max-h-40 overflow-y-auto">
                  {evalResult.rows.map((row) => (
                    <li key={row.startup_id}>
                      {row.startup_id.slice(0, 8)}… {row.status}
                      {row.baseline_verdict != null && row.candidate_verdict != null
                        ? ` ${row.baseline_verdict} → ${row.candidate_verdict}${row.regression ? ' (regression)' : ''}`
                        : ''}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}
      </TabSection>
        </div>
      </details>
      </AnimatedTabBlock>

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

      <AnimatedTabBlock className="px-phi-4 py-phi-5 flex justify-end">
        <button
          onClick={handleTrigger}
          disabled={triggering}
          className="type-meta border border-oxford/20 px-phi-5 py-phi-3 text-oxford/40 hover:text-oxford hover:border-oxford/60 transition-colors uppercase tracking-[0.18em] btn-interaction"
        >
          {triggering ? 'Running...' : 'Run Correction Cycle'}
        </button>
      </AnimatedTabBlock>
    </>
  );
}

/* ─── MAIN COMPONENT ─── */
export default function SystemIntelligence(props: SystemIntelligenceProps) {
  const [activeTab, setActiveTab] = useState<Tab>('thesis');
  const reduceMotion = usePrefersReducedMotion();
  const tabContentContainerVariants = useMemo(
    (): Variants | undefined => (reduceMotion ? undefined : TAB_CONTENT_CONTAINER_VARIANTS),
    [reduceMotion]
  );

  return (
    <div className="w-full font-sans bg-surface-canvas selection:bg-oxford selection:text-paper min-h-full">
      <div className="sticky top-0 z-20 bg-surface-canvas px-phi-4 py-phi-3">
        <div className="flex flex-wrap items-center justify-between gap-x-phi-4 gap-y-phi-2">
          <div className="flex min-w-0 flex-wrap items-center gap-phi-3">
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
        </div>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={reduceMotion ? false : 'hidden'}
          animate="visible"
          exit={reduceMotion ? { opacity: 0 } : { opacity: 0, transform: 'translateY(-4px)' }}
          transition={transitionOrReduced(reduceMotion, { duration: 0.2, ease: tokens.motion.ease })}
          variants={tabContentContainerVariants}
        >
          {activeTab === 'analytics' && (
            <AnalyticsTab
              rejection={props.rejectionAnalytics}
              watchlist={props.watchlistAnalytics}
              concentration={props.concentrationAnalytics}
              systemHealth={props.systemHealth}
            />
          )}
          {activeTab === 'decisions' && (
            <DecisionsTab
              startups={props.startups}
              onStartupClick={props.onStartupClick}
              selectedStartupId={props.selectedStartupId}
            />
          )}
          {activeTab === 'calibration' && (
            <CalibrationTab startups={props.startups} fundConfiguration={props.fundConfiguration} />
          )}
          {activeTab === 'thesis' && (
            <InstitutionalMandateTab
              data={props.fundThesisRuntime}
              loading={props.fundThesisRuntimeLoading}
              error={props.fundThesisRuntimeError}
            />
          )}
          {activeTab === 'meta' && (
            <MetaCommandTab
              reports={props.metaReports}
              weights={props.scoutWeights}
              calibration={props.calibrationState}
              promptState={props.metaPromptState}
              metaEvalSet={props.metaEvalSet}
              insights={props.metaInsights}
            />
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
