/**
 * Internals of the Fund/System Intelligence panel: pure helpers, leaf UI
 * primitives, and the three facet tab components. Extracted verbatim from
 * SystemIntelligence.tsx so that file holds only the orchestrator + nav. All
 * cross-references between these pieces stay within this module.
 */
import { useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { motion, type Variants } from 'framer-motion';
import { Link } from 'react-router';
import { tokens } from '../../design-system/tokens';
import type {
  Startup, RejectionAnalytics,
  MetaCycleReport, MetaPromptState, MetaEvalSet, PromptEvaluateResult, ScoutWeights, CalibrationState,
  HumanFeedbackSummary, MetaInsightsPayload,
  CalibrationChangeSummary, WeightUpdateSummary, PromptMutationSummary,
} from '../../types/startup';
import type { FundThesisRuntime } from '../../api/fundThesis';
import { triggerMetaCycle, promoteMetaPrompt, resetMetaPrompt, saveMetaEvalSet, runPromptEvaluation } from '../../api/meta';
import { transitionOrReduced } from '../../design-system/motion';
import { usePrefersReducedMotion } from '../../hooks';
import EmptyState from '../EmptyState';
import { buildFundIntelligenceSnapshot } from '../../lib/institutionalConviction';
import { formatDate, formatDateTime } from '../../lib/dates';
import { createDefaultFundConfiguration, type FundConfiguration } from '../../lib/fundConfiguration';
import ProposalInbox from '../institutional/ProposalInbox';

export function mandateTagList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((x): x is string => typeof x === 'string' && x.trim().length > 0);
}

export const REVIEWER_EVAL_AGENTS = new Set(['DefaultReviewer', 'SkepticalReviewer', 'OpportunistReviewer']);

export const TAB_CONTENT_CONTAINER_VARIANTS: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.05, delayChildren: 0.03 } },
};

export const TAB_CONTENT_ITEM_VARIANTS: Variants = {
  hidden: { opacity: 0, transform: 'translateY(8px)' },
  visible: {
    opacity: 1,
    transform: 'translateY(0px)',
    transition: { duration: 0.35, ease: tokens.motion.ease },
  },
};

export function AnimatedTabBlock({
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

export function TacticalBar({ pct, delay = 0 }: { pct: number; delay?: number }) {
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

/* ─── INTELLIGENCE ─── */
export function FundIntelligenceSummary({ startups, fundConfiguration }: { startups: Startup[]; fundConfiguration?: FundConfiguration }) {
  const config = fundConfiguration ?? createDefaultFundConfiguration();
  const snapshot = buildFundIntelligenceSnapshot(startups, config);
  const hasDecisions = Object.values(snapshot.decisionsByOutcome).some((count) => count > 0);

  if (!startups.length || !hasDecisions) {
    return (
      <AnimatedTabBlock className="py-phi-6 px-phi-4 flex items-center justify-center">
        <EmptyState
          label="Fund intelligence"
          body="Fund intelligence will emerge as decisions accumulate."
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
              <span className="type-data text-[clamp(22px,2vw,30px)] leading-none text-oxford">{item.value}</span>
              <span className="type-label-section">{item.label}</span>
              {item.detail ? <span className="type-meta text-oxford/60">{item.detail}</span> : null}
            </div>
          ))}
        </div>
      </TabSection>
      <TabSection title="Recurring Risk Themes" label="Observed">
        {snapshot.commonRiskThemes.length ? (
          <ul className="flex flex-col">
            {snapshot.commonRiskThemes.map((item) => (
              <li key={item.theme} className="flex items-baseline justify-between gap-phi-4 border-t border-oxford/[0.06] py-phi-3 first:border-t-0">
                <span className="type-note text-oxford/[0.68]">{item.theme}</span>
                <span className="type-data text-oxford/60">{item.count}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="type-note text-oxford/60 leading-relaxed max-w-xl">
            No recurring risk themes are extractable from the current resolved set.
          </p>
        )}
      </TabSection>
    </>
  );
}

/* ─── SECTION WRAPPER ─── */
export function TabSection({ title, label, children, className = '' }: { title: string; label?: string; children: React.ReactNode; className?: string }) {
  const reduceMotion = usePrefersReducedMotion();
  const header = (
    <div className="flex flex-wrap items-baseline justify-between gap-x-phi-4 gap-y-phi-1">
      <h3 className="type-label-section">{title}</h3>
      {label ? <span className="type-label-section">{label}</span> : null}
    </div>
  );
  const sectionClass = `flex flex-col gap-phi-4 border-t border-oxford/[0.075] px-phi-4 py-phi-6 first:border-t-0 first:pt-phi-4 ${className}`.trim();

  if (reduceMotion) {
    return (
      <section className={sectionClass}>
        {header}
        {children}
      </section>
    );
  }

  return (
    <motion.section
      variants={TAB_CONTENT_ITEM_VARIANTS}
      className={sectionClass}
    >
      {header}
      {children}
    </motion.section>
  );
}

/* ─── STRATEGIC INTELLIGENCE ─── */
export function AnalyticsTab({ rejection }: {
  rejection: RejectionAnalytics;
}) {
  const maxRedFlag = Math.max(...rejection.most_common_red_flags.map((r) => r.count), 1);

  return (
      <TabSection title="Rejection patterns" label="What the fund declines">
        {rejection.most_common_red_flags.length === 0 ? (
          <p className="type-status">No rejection data yet</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-phi-5 gap-y-phi-4">
            {rejection.most_common_red_flags.slice(0, 6).map((rf, i) => (
              <div key={rf.flag} className="flex flex-col gap-phi-2">
                <div className="flex justify-between items-baseline">
                  <span className="type-label-section">{rf.flag.replace(/_/g, ' ')}</span>
                  <span className="type-data text-oxford/60">{rf.count}</span>
                </div>
                <TacticalBar pct={(rf.count / maxRedFlag) * 100} delay={i * 0.05} />
              </div>
            ))}
          </div>
        )}
      </TabSection>
  );
}

/** One line of the mandate spec — mono label register, typographic value. No chips, no boxes. */
export function MandateSpecRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="grid grid-cols-[clamp(110px,18%,160px)_minmax(0,1fr)] items-baseline gap-phi-4 border-t border-oxford/[0.06] py-phi-3 first:border-t-0 first:pt-0">
      <span className="type-label-section">{label}</span>
      {value ? (
        <p className="type-body-sm leading-relaxed text-oxford/[0.78]">{value}</p>
      ) : (
        <p className="type-body-sm text-oxford/60">Not specified</p>
      )}
    </div>
  );
}

export function mandateMoney(value: unknown): string | null {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return null;
  if (n >= 1_000_000) {
    const m = n / 1_000_000;
    return `$${Number.isInteger(m) ? m : m.toFixed(1)}M`;
  }
  if (n >= 1_000) return `$${Math.round(n / 1_000)}K`;
  return `$${n}`;
}

/* ─── FUND THESIS ─── */
export function InstitutionalMandateTab({
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
        <p className="type-status">Loading…</p>
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
  const geographies = mandateTagList(pj.geography);
  const exclusions = mandateTagList(pj.exclusions);
  const preferences = mandateTagList(pj.preferences);
  const riskProfile = typeof pj.risk_profile === 'string' && pj.risk_profile.trim() ? pj.risk_profile.trim() : null;
  const checkMin = mandateMoney(pj.check_size_min);
  const checkMax = mandateMoney(pj.check_size_max);
  const checkSize = checkMin && checkMax ? `${checkMin} – ${checkMax}` : checkMin ?? checkMax;
  const ownershipRaw = Number(pj.ownership_target);
  const ownership = Number.isFinite(ownershipRaw) && ownershipRaw > 0 ? `${ownershipRaw}% target` : null;
  const mandateMode = data.thesis_mode === 'embedding' ? 'AI enhanced' : 'Rule based';

  // The thesis text travels inside `preferences` (with business model and
  // traction lines) — the longest entry is the statement, the rest are notes.
  const statement = preferences.length
    ? preferences.reduce((a, b) => (b.length > a.length ? b : a))
    : null;
  const notes = statement ? preferences.filter((p) => p !== statement) : [];

  return (
    /* Reading room: mandate prose holds its measure on the left; the record
       (version history) fills the region beside it instead of dead paper. */
    <div className="lg:grid lg:grid-cols-[minmax(0,61.8fr)_minmax(0,38.2fr)] lg:items-start lg:gap-x-phi-6">
      <TabSection
        title="The mandate"
        label={`v${data.active_version_number ?? '01'} · ${mandateMode}`}
      >
        {/* The mandate document itself: statement in the house serif, then the
            spec that gates the pipeline — set out, not boxed. */}
        <p className="type-display max-w-[38rem] text-[clamp(18px,1.5vw,24px)] leading-[1.32] text-oxford">
          {statement ??
            'No thesis statement on file. The spec below gates discovery until one is written.'}
        </p>
        {notes.length > 0 ? (
          <div className="mt-phi-3 flex max-w-[38rem] flex-col gap-phi-1">
            {notes.map((line) => (
              <p key={line} className="type-body-sm leading-relaxed text-oxford/60">
                {line}
              </p>
            ))}
          </div>
        ) : null}

        <div className="mt-phi-6 max-w-[44rem]">
          <MandateSpecRow label="Sectors" value={sectors.length ? sectors.join(', ') : null} />
          <MandateSpecRow label="Stages" value={stages.length ? stages.join(', ') : null} />
          <MandateSpecRow label="Geography" value={geographies.length ? geographies.join(', ') : null} />
          <MandateSpecRow label="Check size" value={checkSize ?? null} />
          <MandateSpecRow label="Ownership" value={ownership} />
          <MandateSpecRow label="Excluded" value={exclusions.length ? exclusions.join(', ') : null} />
          <MandateSpecRow label="Risk profile" value={riskProfile} />
        </div>
      </TabSection>

      {(data.version_timeline?.length ?? 0) > 0 && (
        <TabSection title="Version history" className="lg:pt-phi-3">
          <ul className="flex max-w-[44rem] flex-col">
            {(data.version_timeline ?? []).slice(0, 10).map((v) => (
              <li
                key={v.id}
                className="flex flex-wrap items-baseline justify-between gap-phi-3 border-t border-oxford/[0.06] py-phi-3 first:border-t-0 first:pt-0"
              >
                <span className={`type-meta ${v.is_active ? 'text-oxford/80' : 'text-oxford/60'}`}>
                  v{v.version_number}
                  {v.is_active ? ' · active' : ''}
                </span>
                <span className="type-meta tabular-nums text-oxford/60">
                  {formatDate(v.created_at)}
                </span>
              </li>
            ))}
          </ul>
        </TabSection>
      )}
    </div>
  );
}

/* ─── LEARNING HISTORY ─── */
function readableAgentName(value: string): string {
  return value
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\bScout\b/g, 'scouting')
    .replace(/\bReviewer\b/g, 'review')
    .trim();
}

export function LearningTab({
  reports,
  insights,
}: {
  reports: MetaCycleReport[];
  insights: MetaInsightsPayload | null;
}) {
  const latest = reports[0] ?? null;
  const promptChanges = latest?.prompt_proposals?.length
    ? latest.prompt_proposals
    : latest?.mutations_applied ?? [];
  const weightChanges = latest?.weight_proposals?.length
    ? latest.weight_proposals
    : latest?.weight_updates ?? [];
  const calibrationChanges = latest?.calibration_proposals?.length
    ? latest.calibration_proposals
    : latest?.calibration_changes ?? [];
  const feedback = latest?.signal_summary?.human_feedback ?? insights?.signal_summary?.human_feedback;
  const changeCount = promptChanges.length + weightChanges.length + calibrationChanges.length;
  const publishedCount = latest?.production_mutations_applied ?? 0;
  const status = publishedCount > 0
    ? `${publishedCount} governed change${publishedCount === 1 ? '' : 's'} published`
    : changeCount > 0
      ? `${changeCount} change${changeCount === 1 ? '' : 's'} awaiting review`
      : 'No change proposed';

  if (!latest && !insights?.latest) {
    return (
      <AnimatedTabBlock className="px-phi-4 py-phi-6">
        <EmptyState
          label="Learning history"
          body="Aethria will explain what it learns after enough attributed decisions and outcomes have accumulated."
        />
        <Link
          to="/v1/settings?section=governance"
          className="type-action mx-auto mt-phi-4 block w-fit border-b border-oxford/20 pb-1 text-oxford/65 transition-colors hover:text-oxford"
        >
          Open agent governance
        </Link>
      </AnimatedTabBlock>
    );
  }

  const cycleNumber = latest?.cycle_number ?? insights?.latest?.cycle_number;
  const ranAt = latest?.ran_at ?? insights?.latest?.ran_at;
  const why = insights?.why?.length ? insights.why : latest?.no_action_reasons ?? [];

  return (
    <>
      <AnimatedTabBlock className="px-phi-4 pb-phi-5 pt-phi-4">
        <p className="type-body max-w-2xl leading-relaxed text-oxford/70">
          This is the fund’s learning record: what Aethria observed in your rulings,
          what it proposed changing, and whether that change reached production.
        </p>
      </AnimatedTabBlock>

      <TabSection
        title={cycleNumber != null ? `Learning cycle ${cycleNumber}` : 'Latest learning cycle'}
        label={ranAt ? formatDate(ranAt) : undefined}
      >
        <p className="type-display max-w-[42rem] text-[clamp(20px,2vw,28px)] leading-[1.3] text-oxford">
          {status}
        </p>
        {feedback && feedback.recent_count > 0 ? (
          <p className="type-body-sm max-w-[44rem] leading-relaxed text-oxford/65">
            Based on {feedback.recent_count} attributed ruling{feedback.recent_count === 1 ? '' : 's'}:
            {' '}{feedback.by_outcome.YES} invest, {feedback.by_outcome.MAYBE} monitor, and {feedback.by_outcome.NO} pass.
            {feedback.disagreed_with_ai_count > 0
              ? ` ${feedback.disagreed_with_ai_count} differed from Aethria’s recommendation.`
              : ''}
          </p>
        ) : (
          <p className="type-body-sm text-oxford/60">
            No attributed human-feedback sample was recorded for this cycle.
          </p>
        )}
      </TabSection>

      {changeCount > 0 ? (
        <TabSection
          title={publishedCount > 0 ? 'What changed' : 'What Aethria proposes'}
          label={publishedCount > 0 ? 'Governed' : 'Awaiting operator review'}
        >
          <div className="flex max-w-[48rem] flex-col">
            {promptChanges.map((change, index) => (
              <div key={`prompt-${change.agent_target}-${index}`} className="border-t border-oxford/[0.06] py-phi-3 first:border-t-0 first:pt-0">
                <p className="type-body-sm text-oxford/75">
                  Refine {readableAgentName(change.agent_target)}
                </p>
                {change.reasoning ? <p className="type-note mt-phi-1 leading-relaxed text-oxford/60">{change.reasoning}</p> : null}
              </div>
            ))}
            {weightChanges.map((change, index) => (
              <div key={`weight-${change.agent_target}-${index}`} className="border-t border-oxford/[0.06] py-phi-3 first:border-t-0 first:pt-0">
                <p className="type-body-sm text-oxford/75">
                  Rebalance {readableAgentName(change.agent_target)}
                </p>
                <p className="type-note mt-phi-1 tabular-nums text-oxford/60">
                  {Math.round(change.previous_weight * 100)}% → {Math.round(change.new_weight * 100)}%
                </p>
              </div>
            ))}
            {calibrationChanges.map((change, index) => (
              <div key={`calibration-${change.parameter}-${index}`} className="border-t border-oxford/[0.06] py-phi-3 first:border-t-0 first:pt-0">
                <p className="type-body-sm text-oxford/75">
                  {change.parameter.replace(/_/g, ' ')}
                  {change.direction ? ` · ${change.direction}` : ''}
                </p>
                {change.reasoning ? <p className="type-note mt-phi-1 leading-relaxed text-oxford/60">{change.reasoning}</p> : null}
              </div>
            ))}
          </div>
        </TabSection>
      ) : null}

      {why.length > 0 ? (
        <TabSection title="Why no further change" label="Evidence threshold">
          <div className="flex max-w-[44rem] flex-col gap-phi-2 border-l border-oxford/20 pl-phi-4">
            {why.map((line, index) => (
              <p key={index} className="type-note leading-relaxed text-oxford/60">{line}</p>
            ))}
          </div>
        </TabSection>
      ) : null}

      <AnimatedTabBlock className="px-phi-4 pb-phi-6 pt-phi-3">
        <Link
          to="/v1/settings?section=governance"
          className="type-action inline-block border-b border-oxford/20 pb-1 text-oxford/65 transition-colors hover:text-oxford"
        >
          Review advanced agent governance →
        </Link>
      </AnimatedTabBlock>
    </>
  );
}

/* ─── AGENT GOVERNANCE ─── */
/** Cycle readout — same numeral register as the pipeline strip. */
export function MetaReadout({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col gap-phi-1">
      <span className="type-data text-[clamp(18px,1.6vw,24px)] leading-none text-oxford">
        {value}
      </span>
      <span className="type-label-section">{label}</span>
    </div>
  );
}

export function RunCycleButton({ triggering, onTrigger }: { triggering: boolean; onTrigger: () => void }) {
  return (
    <button
      type="button"
      onClick={onTrigger}
      disabled={triggering}
      className="type-action border border-oxford/20 px-phi-5 py-phi-3 hover:text-oxford hover:border-oxford/60 transition-colors btn-interaction"
    >
      {triggering ? 'Running…' : 'Run correction cycle'}
    </button>
  );
}

export function MetaCommandTab({ reports, weights, calibration, promptState, metaEvalSet, insights, fundConfiguration }: {
  reports: MetaCycleReport[];
  weights: ScoutWeights;
  calibration: CalibrationState;
  promptState: MetaPromptState;
  metaEvalSet: MetaEvalSet;
  insights: MetaInsightsPayload | null;
  fundConfiguration?: FundConfiguration;
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
  const weightProposalCount = (lastReport?.weight_proposals ?? lastReport?.weight_updates ?? []).length;
  const calibrationCount = (lastReport?.calibration_proposals ?? lastReport?.calibration_changes ?? []).length;
  const productionAppliedCount = lastReport?.production_mutations_applied ?? 0;

  const agentFromLibraryKey = (libraryKey: string) => libraryKey.split(':')[0] ?? '';

  const humanFb: HumanFeedbackSummary | undefined =
    lastReport?.signal_summary?.human_feedback ?? insights?.signal_summary?.human_feedback;
  const humanFbLine =
    humanFb && humanFb.recent_count > 0
      ? `Recorded ${humanFb.recent_count} analyst confirmations in the last correction signal (Invest ${humanFb.by_outcome?.YES ?? 0}, Pass ${humanFb.by_outcome?.NO ?? 0}, Monitor ${humanFb.by_outcome?.MAYBE ?? 0}${humanFb.disagreed_with_ai_count ? `; ${humanFb.disagreed_with_ai_count} differed from the AI recommendation at resolve time` : ''}).`
      : null;

  const wc = insights?.what_changed;
  const insightPromptCount = Math.max(wc?.mutations_applied?.length ?? 0, wc?.prompt_proposals?.length ?? 0);
  const insightWeightCount = Math.max(wc?.weight_proposals?.length ?? 0, wc?.weight_updates?.length ?? 0);
  const insightCalibrationCount = Math.max(wc?.calibration_proposals?.length ?? 0, wc?.calibration_changes?.length ?? 0);
  const whatChangedTotal = insightPromptCount + insightWeightCount + insightCalibrationCount;
  const insightMutations = (
    (wc?.mutations_applied?.length ? wc.mutations_applied : wc?.prompt_proposals) ?? []
  ) as PromptMutationSummary[];
  const insightWeights = (wc?.weight_updates ?? []) as WeightUpdateSummary[];
  const insightCalibrations = (wc?.calibration_changes ?? []) as CalibrationChangeSummary[];
  const showLatestInsight =
    !!insights?.latest && ((insights?.why?.length ?? 0) > 0 || whatChangedTotal > 0);

  // One cycle story: prefer the rich insight payload, fall back to the raw report.
  const useInsight = showLatestInsight;
  const hasCycle = useInsight || lastReport != null;
  const cycleNumber = useInsight ? insights?.latest?.cycle_number : lastReport?.cycle_number;
  const cycleRanAt = (useInsight ? insights?.latest?.ran_at : lastReport?.ran_at) ?? null;
  const cyclePromptCount = useInsight ? insightPromptCount : proposalCount;
  const cycleWeightCount = useInsight ? insightWeightCount : weightProposalCount;
  const cycleCalibrationCount = useInsight ? insightCalibrationCount : calibrationCount;
  const whyLines = (insights?.why?.length ? insights.why : lastReport?.no_action_reasons) ?? [];

  return (
    <>
      <AnimatedTabBlock className="px-phi-4 pt-phi-4 pb-phi-5 border-b border-oxford/[0.06]">
        <p className="type-body text-oxford/65 leading-relaxed max-w-2xl">
          The correction cycle analyses attributed rulings and outcomes, then proposes updates to prompts,
          thresholds, and scoring weights. Proposals stay out of production until an operator previews,
          reviews, and publishes a governed policy version.
        </p>
        <p className="type-status mt-phi-3">
          {lastReport?.analysis_only === false ? 'Governed promotion recorded' : 'Analysis only · production unchanged'}
        </p>
        {humanFbLine && (
          <p className="type-note max-w-2xl mt-phi-3 text-oxford/60">{humanFbLine}</p>
        )}
      </AnimatedTabBlock>
      <AnimatedTabBlock className="border-b border-oxford/[0.06] px-phi-4 py-phi-5">
        <ProposalInbox fundConfig={(fundConfiguration ?? createDefaultFundConfiguration()) as unknown as Record<string, unknown>} />
      </AnimatedTabBlock>
      {/* One cycle section — readouts, what changed, why. The old page rendered
          "Latest insight" and "Last Cycle" as near-duplicates stacked. */}
      {hasCycle ? (
        <TabSection title="Correction cycle" label={cycleRanAt ? formatDate(cycleRanAt) : undefined}>
          <div className="flex flex-wrap gap-phi-6">
            {typeof cycleNumber === 'number' && <MetaReadout label="Cycle" value={cycleNumber} />}
            <MetaReadout label="Prompt proposals" value={cyclePromptCount} />
            <MetaReadout label="Weight proposals" value={cycleWeightCount} />
            <MetaReadout label="Calibration proposals" value={cycleCalibrationCount} />
            <MetaReadout label="Applied" value={productionAppliedCount} />
          </div>
          {useInsight && whatChangedTotal > 0 && (
            <div className="mt-phi-3 flex max-w-[44rem] flex-col">
              {insightMutations.map((m, i) => (
                <p key={`mut-${m.agent_target}-${i}`} className="type-note text-oxford/60 border-t border-oxford/[0.06] py-phi-3 first:border-t-0 first:pt-0">
                  <span className="text-oxford/70">{m.agent_target}</span>
                  {m.reasoning ? ` — ${m.reasoning}` : ''}
                </p>
              ))}
              {insightWeights.map((w, i) => (
                <p key={`wt-${w.agent_target}-${i}`} className="type-note text-oxford/60 border-t border-oxford/[0.06] py-phi-3 first:border-t-0 first:pt-0 tabular-nums">
                  {w.agent_target}: {Math.round((w.previous_weight ?? 0) * 100)}% → {Math.round((w.new_weight ?? 0) * 100)}%
                </p>
              ))}
              {insightCalibrations.map((c, i) => (
                <p key={`cal-${c.parameter}-${i}`} className="type-note text-oxford/60 border-t border-oxford/[0.06] py-phi-3 first:border-t-0 first:pt-0">
                  <span className="text-oxford/70">{c.parameter.replace(/_/g, ' ')}</span>
                  {c.direction ? ` (${c.direction})` : ''}
                  {c.reasoning ? ` — ${c.reasoning}` : ''}
                </p>
              ))}
            </div>
          )}
          {whyLines.length > 0 && (
            <div className="mt-phi-4 flex max-w-[44rem] flex-col gap-phi-2 border-l border-oxford/20 pl-phi-4">
              <span className="type-label-section">Why no further action</span>
              {whyLines.map((line, i) => (
                <p key={i} className="type-note text-oxford/60">{line}</p>
              ))}
            </div>
          )}
          <div className="mt-phi-5">
            <RunCycleButton triggering={triggering} onTrigger={handleTrigger} />
          </div>
        </TabSection>
      ) : (
        <TabSection title="Correction cycle">
          <p className="type-status">No cycles run yet</p>
          <div className="mt-phi-4">
            <RunCycleButton triggering={triggering} onTrigger={handleTrigger} />
          </div>
        </TabSection>
      )}

      <AnimatedTabBlock>
      <details className="group border-b border-oxford/[0.06]">
        <summary className="type-action cursor-pointer list-none px-phi-4 py-phi-4 hover:text-oxford/70 marker:content-none flex items-center justify-between gap-phi-3">
          <span>Advanced — prompt checks (optional)</span>
          <span className="type-action group-open:hidden">Show</span>
          <span className="type-action hidden group-open:inline">Hide</span>
        </summary>
        <div className="flex flex-col pb-phi-2">
        <p className="type-body text-oxford/60 leading-relaxed px-phi-4 pt-phi-3 max-w-2xl">
          You can ignore this unless the correction cycle has produced <span className="text-oxford/75">pending prompt drafts</span> and you want to test or turn them on.
          Day-to-day deal work and your Invest / Pass / Monitor confirmations do not depend on anything here—the product runs on built-in prompts until you explicitly promote a draft.
        </p>
      <TabSection title="Bench list" label="For Evaluate only">
        <p className="type-note mb-phi-3 max-w-2xl text-oxford/60">
          Paste internal startup IDs from your pipeline (one per line, up to {metaEvalSet.max}). When you press <span className="text-oxford/65">Evaluate</span> on a pending <em>reviewer</em> prompt, the system re-runs that reviewer on these deals with the proposed instructions and compares to saved scores—cheap guardrail before going live. Each ID is one extra model call.
        </p>
        <textarea
          value={evalDraft}
          onChange={(e) => setEvalDraft(e.target.value)}
          rows={5}
          className="w-full max-w-2xl type-meta text-oxford/70 bg-oxford/[0.03] border border-oxford/[0.1] px-phi-3 py-phi-2 resize-y"
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
            className="type-action border border-oxford/15 px-phi-4 py-phi-2 hover:text-oxford hover:border-oxford/40 btn-interaction"
          >
            Save bench list
          </button>
          <span className="type-meta text-oxford/60">Saved: {metaEvalSet.count}</span>
        </div>
        {evalSaveNote && <p className="type-meta text-oxford/60 mt-phi-2">{evalSaveNote}</p>}
      </TabSection>

      <TabSection title="Prompt drafts" label="Active vs pending">
        <p className="type-note mb-phi-3 max-w-2xl text-oxford/60">
          The meta cycle can propose new instructions for scouts/reviewers. <span className="text-oxford/65">Active</span> is what runs today (empty = product defaults).
          <span className="text-oxford/65"> Pending</span> is queued proposals—use <span className="text-oxford/65">Promote</span> to make one live, or <span className="text-oxford/65">Reset</span> to drop back to defaults.
          Your org may require a passing <span className="text-oxford/65">Evaluate</span> before Promote for reviewers.
        </p>
        {promptState.restart_note && (
          <p className="type-note mb-phi-3 max-w-2xl text-oxford/60">{promptState.restart_note}</p>
        )}
        <div className="flex flex-col gap-phi-4">
          <div>
            <span className="type-status mb-phi-2 block">Active (live)</span>
            {Object.keys(promptState.active).length === 0 ? (
              <p className="type-meta text-oxford/60">None—using built-in prompts.</p>
            ) : (
              <div className="flex flex-col divide-y divide-oxford/[0.06] border-y border-oxford/[0.06]">
                {Object.entries(promptState.active).map(([agent, libKey]) => (
                  <div key={agent} className="flex flex-wrap items-center justify-between gap-phi-3 py-phi-3">
                    <div className="min-w-0">
                      <span className="type-meta text-oxford/70">{agent}</span>
                      <p className="type-meta text-oxford/60 truncate max-w-xl" title={libKey}>{libKey}</p>
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
                      className="type-action border border-oxford/15 px-phi-3 py-phi-2 hover:text-oxford hover:border-oxford/40 btn-interaction shrink-0"
                    >
                      {promptBusy === agent ? '…' : 'Use built-in default'}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div>
            <span className="type-status mb-phi-2 block">Pending (not live yet)</span>
            {promptState.pending.length === 0 ? (
              <p className="type-meta text-oxford/60">Nothing queued—defaults or only active prompts.</p>
            ) : (
              <div className="flex flex-col divide-y divide-oxford/[0.06] border-y border-oxford/[0.06] max-h-[280px] overflow-y-auto">
                {promptState.pending.map((p) => {
                  const agent = agentFromLibraryKey(p.library_key);
                  const canEval = REVIEWER_EVAL_AGENTS.has(agent);
                  return (
                    <div key={p.library_key} className="flex flex-wrap items-start justify-between gap-phi-3 py-phi-3">
                      <div className="min-w-0 flex-1">
                        <span className="type-meta text-oxford/70">{agent}</span>
                        <p className="type-meta text-oxford/60 break-all">{p.library_key}</p>
                        {p.reasoning && (
                          <p className="type-meta text-oxford/60 mt-phi-1 line-clamp-2">{p.reasoning}</p>
                        )}
                        <p className="type-meta text-oxford/60 mt-phi-1">
                          {p.prompt_char_count != null ? `${p.prompt_char_count} chars` : ''}
                          {p.created_at ? ` · ${formatDateTime(p.created_at)}` : ''}
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
                            className="type-action border border-oxford/15 px-phi-3 py-phi-2 hover:text-oxford hover:border-oxford/40 btn-interaction"
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
                          className="type-action border border-oxford/15 px-phi-3 py-phi-2 hover:text-oxford hover:border-oxford/40 btn-interaction"
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
          <div className="mt-phi-4 max-w-3xl border-t border-oxford/[0.08] pt-phi-3">
            <span className="type-label-section mb-phi-2 block">Last evaluation</span>
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
                  <p className="text-oxford/60">Truncated to {evalResult.max_startups} startups.</p>
                )}
              </div>
            )}
            {evalResult.rows && evalResult.rows.length > 0 && (
              <details className="mt-phi-3">
                <summary className="type-meta text-oxford/60 cursor-pointer">Per startup</summary>
                <ul className="mt-phi-2 space-y-phi-1 type-meta text-oxford/60 max-h-40 overflow-y-auto">
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
                <span className="type-label-section">{name}</span>
                <span className="type-data text-oxford/60">{Math.round(w * 100)}%</span>
              </div>
              <TacticalBar pct={w * 100} delay={i * 0.1} />
            </div>
          ))}
        </div>
      </TabSection>

      <TabSection title="Calibration Log">
        {calibration.calibration_history.length === 0 ? (
          <p className="type-status">No calibration history yet</p>
        ) : (
          <div className="flex flex-col">
            {calibration.calibration_history.slice(-5).reverse().map((h, i) => (
              <div key={i} className="grid grid-cols-[110px_1fr] items-start gap-phi-4 border-t border-oxford/[0.06] py-phi-3 first:border-t-0 first:pt-0">
                <span
                  className={`type-status ${
                    h.direction === 'tightened' ? 'text-escalation/85' : 'text-oxford/60'
                  }`}
                >
                  {h.direction}
                </span>
                <div className="flex min-w-0 flex-col gap-phi-1">
                  <span className="type-meta text-oxford/70">{h.parameter.replace(/_/g, ' ')}</span>
                  <p className="type-meta leading-relaxed text-oxford/60">{h.reasoning}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </TabSection>

    </>
  );
}

/* ─── MAIN COMPONENT ─── */
