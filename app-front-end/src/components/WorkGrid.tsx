import { useMemo, useState, useCallback, useRef } from 'react';
import { motion, AnimatePresence, type Variants } from 'framer-motion';
import type { Startup } from '../types/startup';
import { getReviewerQualityBand } from '../design-system/semantics';
import { tokens } from '../design-system/tokens';
import { usePrefersReducedMotion } from '../hooks';
import DecisionBadge from './DecisionBadge';
import VerdictBandBadge from './VerdictBandBadge';
import EmptyState from './EmptyState';
import { productInteraction, productText } from '../design-system/productSystem';
import { getDecisionBadgeVariant } from '../lib/decisionBadgeVariant';
import {
  getDealAgeDays,
  getDealQueueState,
  isDealDecided,
  queueAttentionRank,
  type RulingDecision,
} from '../lib/dealState';
import { extractAdverseRegister } from '../lib/adverseRegister';
import {
  bandForScore,
  computeConfiguredScore,
  createDefaultFundConfiguration,
  isStartupStaleByConfig,
  type FundConfiguration,
} from '../lib/fundConfiguration';

type SourceFilter = 'ALL' | 'SCOUT' | 'LOOKUP';
type DecisionFilter =
  | 'ALL'
  | 'NEEDS_RULING'
  | 'STALE'
  | 'ADVERSE'
  | 'YES'
  | 'NO'
  | 'MAYBE'
  | 'ESCALATION'
  | 'WATCHLIST'
  | 'DECIDED'
  | 'AWAITING_REVIEW';
type ReviewFilter = 'ALL' | 'STRONG' | 'MEDIUM' | 'WEAK' | 'UNREVIEWED';
type SortFilter = 'QUEUE_PRIORITY' | 'NEWEST' | 'OLDEST' | 'UNRESOLVED_OLDEST' | 'CONFIDENCE_HIGH' | 'CONFIDENCE_LOW' | 'NAME_AZ';

function getReviewerVerdict(s: Startup) {
  return getReviewerQualityBand(s.review);
}

function getSourceBadge(startup: Startup): 'LOOKUP' | 'SCOUT' {
  return (startup.scout.origin_type ?? '').toLowerCase() === 'on_demand_lookup' ? 'LOOKUP' : 'SCOUT';
}

function sortKey(s: Startup): string {
  return s.timestamps?.partnered_at ?? s.timestamps?.reviewed_at ?? s.timestamps?.discovered_at ?? '';
}

function getHumanDecision(startup: Startup): RulingDecision | null {
  return startup.human_resolution?.decision ?? null;
}

function startupNeedsRuling(startup: Startup): boolean {
  return !isDealDecided(startup) && Boolean(startup.review || startup.partner?.recommendation);
}

const FilterButton = ({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) => (
  <button
    type="button"
    onClick={onClick}
    aria-pressed={active}
    className={`type-meta uppercase tracking-[0.12em] min-h-[36px] px-phi-3 transition-colors btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 ${active ? 'text-oxford font-semibold' : 'text-oxford/40 hover:text-oxford/70'
      }`}
  >
    {label}
  </button>
);

function AdvancedChip({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`type-meta min-h-[36px] whitespace-nowrap px-phi-3 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 ${active ? 'bg-oxford text-paper' : 'bg-oxford/[0.035] hover:bg-oxford/[0.065] text-oxford/58'}`}
    >
      {label}
    </button>
  );
}

interface WorkGridProps {
  startups: Startup[];
  onStartupClick: (startup: Startup) => void;
  selectedId?: string | null;
  watchlistIds?: Set<string>;
  fundConfiguration?: FundConfiguration;
}

const EMPTY_WATCHLIST_IDS = new Set<string>();

const ATTENTION_FILTER_CHIPS: { key: DecisionFilter; label: string }[] = [
  { key: 'ALL', label: 'ANY ATTENTION' },
  { key: 'NEEDS_RULING', label: 'NEEDS RULING' },
  { key: 'STALE', label: 'STALE' },
  { key: 'ADVERSE', label: 'ADVERSE' },
  { key: 'ESCALATION', label: 'ESCALATION' },
  { key: 'AWAITING_REVIEW', label: 'AWAITING REVIEW' },
  { key: 'WATCHLIST', label: 'ON MONITOR' },
];

const RULING_FILTER_CHIPS: { key: DecisionFilter; label: string }[] = [
  { key: 'YES', label: 'INVEST' },
  { key: 'MAYBE', label: 'MONITOR' },
  { key: 'NO', label: 'PASS' },
  { key: 'DECIDED', label: 'ANY DECIDED' },
];

interface WorkGridRow {
  startup: Startup;
  sourceBadge: 'LOOKUP' | 'SCOUT';
  reviewBand: ReturnType<typeof getReviewerVerdict>;
  decisionVariant: ReturnType<typeof getDecisionBadgeVariant>;
  queueState: ReturnType<typeof getDealQueueState>;
  adverseItems: ReturnType<typeof extractAdverseRegister>;
  configuredScore: number;
  configuredBand: string;
  hasAdverse: boolean;
  hasHighAdverse: boolean;
  ageDays: number | null;
  displayIndex: string;
  onMonitorList: boolean;
  isDecided: boolean;
  isStale: boolean;
  isEscalated: boolean;
  needsRuling: boolean;
  sortKeyValue: string;
  unresolvedAt: string | null;
}

function formatRowDate(value: string): string {
  if (!value) return '';
  return new Date(value).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
}

function formatUnresolvedAgeDays(value: string): string {
  const time = new Date(value).getTime();
  if (!Number.isFinite(time)) return '';
  const days = Math.max(0, Math.floor((Date.now() - time) / (24 * 60 * 60 * 1000)));
  return `${days} day${days === 1 ? '' : 's'}`;
}

function getUnresolvedAt(startup: Startup): string | null {
  return startup.unresolved_at ?? startup.timestamps?.unresolved_at ?? null;
}

function getRowAttention(row: WorkGridRow): { label: string; reason: string; tone: 'critical' | 'watch' | 'active' | 'quiet' } {
  const { startup } = row;
  const firstAdverse = row.adverseItems[0];
  if (row.isDecided) {
    const decision = getHumanDecision(startup);
    return {
      label: decision === 'YES' ? 'Invested' : decision === 'NO' ? 'Passed' : 'Monitoring',
      reason: startup.human_resolution?.notes?.trim() || 'Human ruling recorded.',
      tone: 'quiet',
    };
  }
  if (row.isEscalated || row.hasHighAdverse) {
    return {
      label: row.isEscalated ? 'Escalation' : 'Red flag',
      reason: firstAdverse?.title || 'Human review required before conviction can form.',
      tone: 'critical',
    };
  }
  if (row.isStale) {
    return {
      label: 'Aging',
      reason: row.ageDays != null ? `${row.ageDays} days unresolved; either rule or deliberately keep on monitor.` : 'Unresolved beyond the configured stale threshold.',
      tone: 'watch',
    };
  }
  if (row.needsRuling) {
    const recommendation = startup.partner?.recommendation
      ? `Partner recommends ${startup.partner.recommendation.toLowerCase()}.`
      : 'Review is complete and ready for judgment.';
    return {
      label: 'Ready',
      reason: startup.partner?.snapshot?.key_signal?.trim() || startup.partner?.decision_drivers?.[0] || recommendation,
      tone: 'active',
    };
  }
  if (startup.review) {
    return {
      label: 'Reviewed',
      reason: startup.review.aethria_view?.focal_question?.trim() || startup.review.overall_summary?.trim() || 'Reviewer output is available.',
      tone: 'active',
    };
  }
  return {
    label: 'Awaiting review',
    reason: startup.scout.biggest_unknown?.trim() || startup.scout.one_line?.trim() || 'Scout discovery is queued for reviewer judgment.',
    tone: 'quiet',
  };
}

function truncateRowReason(value: string): string {
  const text = value.replace(/\s+/g, ' ').trim();
  return text.length > 150 ? `${text.slice(0, 147).trim()}...` : text;
}

function rowMatchesDecisionFilter(row: WorkGridRow, filter: DecisionFilter): boolean {
  if (filter === 'ALL') return true;
  if (filter === 'WATCHLIST') return row.onMonitorList;
  if (filter === 'NEEDS_RULING') return row.needsRuling;
  if (filter === 'STALE') return row.isStale;
  if (filter === 'ADVERSE') return !row.isDecided && row.hasAdverse;
  if (filter === 'ESCALATION') return !row.isDecided && row.isEscalated;
  if (filter === 'DECIDED') return row.isDecided;
  if (filter === 'AWAITING_REVIEW') {
    return !row.startup.review && !row.startup.partner?.recommendation && !row.isDecided;
  }
  return getHumanDecision(row.startup) === filter;
}

const WorkGrid = ({ startups, onStartupClick, selectedId, watchlistIds, fundConfiguration }: WorkGridProps): JSX.Element => {
  const watchlistSet = watchlistIds ?? EMPTY_WATCHLIST_IDS;
  const config = fundConfiguration ?? createDefaultFundConfiguration();
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('ALL');
  const [decisionFilter, setDecisionFilter] = useState<DecisionFilter>('ALL');
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>('ALL');
  const [sortFilter, setSortFilter] = useState<SortFilter>('QUEUE_PRIORITY');
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const reduceMotion = usePrefersReducedMotion();
  const hasActiveFilters =
    sourceFilter !== 'ALL' ||
    decisionFilter !== 'ALL' ||
    reviewFilter !== 'ALL' ||
    sortFilter !== 'QUEUE_PRIORITY';

  const resetFilters = useCallback(() => {
    setSourceFilter('ALL');
    setDecisionFilter('ALL');
    setReviewFilter('ALL');
    setSortFilter('QUEUE_PRIORITY');
  }, []);

  const listContainerVariants = useMemo((): Variants | undefined =>
    reduceMotion
      ? undefined
      : {
          hidden: {},
          // 40ms stagger stays within the local motion guideline and feels snappy.
          visible: { transition: { staggerChildren: 0.04, delayChildren: 0.04 } },
        },
    [reduceMotion]
  );
  // y-axis entry matches natural reading/scroll direction; x-axis entry is arbitrary
  const rowVariants = useMemo((): Variants | undefined =>
    reduceMotion
      ? undefined
      : {
          hidden: { opacity: 0, transform: 'translateY(6px)' },
          visible: {
            opacity: 1,
            transform: 'translateY(0px)',
            transition: { duration: tokens.motion.duration.short, ease: tokens.motion.ease },
          },
        },
    [reduceMotion]
  );

  // Ref array for keyboard navigation between rows
  const rowRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  const stableIndex = useMemo(() => {
    // Reference numbers are always chronological by discovery (oldest = 01), independent of sort
    const byDiscovery = [...startups].sort((a, b) => sortKey(a).localeCompare(sortKey(b)));
    return new Map(byDiscovery.map((s, i) => [s.id, i + 1]));
  }, [startups]);

  const orderedRows = useMemo(() => {
    const rows: WorkGridRow[] = startups.map((startup) => {
      const adverseItems = extractAdverseRegister(startup);
      const queueState = getDealQueueState(startup);
      const isDecided = isDealDecided(startup);
      const configuredScore = computeConfiguredScore(startup, config);
      const isStale = isStartupStaleByConfig(startup, config);
      const unresolvedAt = getUnresolvedAt(startup);
      const displayIndex = (stableIndex.get(startup.id) ?? 0).toString().padStart(2, '0');
      return {
        startup,
        sourceBadge: getSourceBadge(startup),
        reviewBand: getReviewerVerdict(startup),
        decisionVariant: getDecisionBadgeVariant(startup),
        queueState,
        adverseItems,
        configuredScore,
        configuredBand: bandForScore(configuredScore, config.scoreBands).label,
        hasAdverse: adverseItems.length > 0,
        hasHighAdverse: adverseItems.some((item) => item.severity === 'high'),
        ageDays: getDealAgeDays(startup),
        displayIndex,
        onMonitorList: watchlistSet.has(startup.id),
        isDecided,
        isStale,
        isEscalated: queueState === 'escalated',
        needsRuling: startupNeedsRuling(startup),
        sortKeyValue: sortKey(startup),
        unresolvedAt,
      };
    });
    const sorted = [...rows];
    switch (sortFilter) {
      case 'QUEUE_PRIORITY':
        sorted.sort((a, b) => {
          const ar = a.isDecided ? 4 : a.hasHighAdverse || a.isEscalated ? 0 : a.isStale ? 1 : a.startup.review ? 2 : queueAttentionRank(a.startup);
          const br = b.isDecided ? 4 : b.hasHighAdverse || b.isEscalated ? 0 : b.isStale ? 1 : b.startup.review ? 2 : queueAttentionRank(b.startup);
          if (ar !== br) return ar - br;
          return b.sortKeyValue.localeCompare(a.sortKeyValue);
        });
        break;
      case 'OLDEST':
        sorted.sort((a, b) => a.sortKeyValue.localeCompare(b.sortKeyValue));
        break;
      case 'UNRESOLVED_OLDEST':
        sorted.sort((a, b) => (a.unresolvedAt ?? '9999').localeCompare(b.unresolvedAt ?? '9999'));
        break;
      case 'CONFIDENCE_HIGH':
        sorted.sort((a, b) => (b.startup.scout.confidence ?? 0) - (a.startup.scout.confidence ?? 0));
        break;
      case 'CONFIDENCE_LOW':
        sorted.sort((a, b) => (a.startup.scout.confidence ?? 0) - (b.startup.scout.confidence ?? 0));
        break;
      case 'NAME_AZ':
        sorted.sort((a, b) => (a.startup.scout.name ?? '').localeCompare(b.startup.scout.name ?? ''));
        break;
      case 'NEWEST':
      default:
        sorted.sort((a, b) => b.sortKeyValue.localeCompare(a.sortKeyValue));
        break;
    }
    const filtered = sorted.filter((row) => {
      if (sourceFilter === 'LOOKUP' && row.sourceBadge !== 'LOOKUP') return false;
      if (sourceFilter === 'SCOUT' && row.sourceBadge !== 'SCOUT') return false;
      if (!rowMatchesDecisionFilter(row, decisionFilter)) return false;
      if (reviewFilter === 'UNREVIEWED' && row.startup.review != null) return false;
      if (reviewFilter !== 'ALL' && reviewFilter !== 'UNREVIEWED' && row.reviewBand !== reviewFilter) return false;
      return true;
    });
    return filtered;
  }, [startups, stableIndex, sourceFilter, decisionFilter, reviewFilter, sortFilter, watchlistSet, config]);

  // Arrow-key navigation between rows for power-user keyboard flow.
  const handleRowKeyDown = useCallback(
    (e: React.KeyboardEvent, row: (typeof orderedRows)[number], idx: number) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onStartupClick(row.startup);
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        const next = orderedRows[idx + 1];
        if (next) rowRefs.current.get(next.startup.id)?.focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const prev = orderedRows[idx - 1];
        if (prev) rowRefs.current.get(prev.startup.id)?.focus();
      }
    },
    [onStartupClick, orderedRows]
  );

  if (startups.length === 0) {
    return (
      <div className="w-full h-full min-h-[12rem] flex flex-col items-center justify-center">
        <EmptyState
          label="Decision queue"
          body={`Scouts are filling the workspace against the active mandate. Stale pressure begins after ${config.thresholds.staleAfterHours} hours.`}
        />
      </div>
    );
  }

  return (
    <div className="w-full font-sans bg-surface-canvas selection:bg-oxford selection:text-paper">
      <header className="sticky top-0 z-20 border-b border-oxford/[0.08] bg-paper px-phi-3 py-phi-2 uppercase tracking-[0.06em]">
        <div className="flex min-w-0 flex-col gap-phi-2">
          <div className="min-w-0 flex flex-col gap-phi-1">
            <p className={productText.mutedLabel}>Decision queue</p>
            <p className="type-meta normal-case tracking-normal text-oxford/32">
              {config.thresholds.staleAfterHours}h stale · {config.risk.sensitivity} risk
            </p>
          </div>

          <div className="flex min-w-0 flex-wrap items-center gap-x-phi-3 gap-y-phi-1">
            <div className="flex items-center gap-0" role="group" aria-label="Deal source filters">
              <FilterButton active={sourceFilter === 'ALL'} label="ALL" onClick={() => setSourceFilter('ALL')} />
              <FilterButton active={sourceFilter === 'SCOUT'} label="SCOUT" onClick={() => setSourceFilter('SCOUT')} />
              <FilterButton active={sourceFilter === 'LOOKUP'} label="LOOKUP" onClick={() => setSourceFilter('LOOKUP')} />
            </div>

            <div className="ml-auto flex items-center gap-x-phi-3">
              <div className="relative shrink-0">
                <select
                  value={sortFilter}
                  onChange={(e) => setSortFilter(e.target.value as SortFilter)}
                  aria-label="Sort deals"
                  className="appearance-none min-h-[36px] border-b border-transparent bg-transparent type-meta text-oxford/38 hover:text-oxford/70 transition-colors pr-6 text-right outline-none cursor-pointer focus-visible:border-oxford/45 focus-visible:text-oxford"
                >
                  <option value="QUEUE_PRIORITY">PRIORITY</option>
                  <option value="NEWEST">NEWEST</option>
                  <option value="OLDEST">OLDEST</option>
                  <option value="UNRESOLVED_OLDEST">UNRESOLVED</option>
                  <option value="CONFIDENCE_HIGH">SIGNAL ↓</option>
                  <option value="CONFIDENCE_LOW">SIGNAL ↑</option>
                  <option value="NAME_AZ">NAME A–Z</option>
                </select>
                <span className="pointer-events-none absolute right-0 top-1/2 -translate-y-1/2 text-oxford/20" aria-hidden>
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 9l6 6 6-6" /></svg>
                </span>
              </div>

              <button
                type="button"
                onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
                aria-expanded={showAdvancedFilters}
                className={`type-meta uppercase tracking-[0.12em] min-h-[36px] px-phi-3 transition-colors btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 shrink-0 ${showAdvancedFilters ? 'text-oxford font-semibold' : 'text-oxford/40 hover:text-oxford/70'}`}
              >
                {showAdvancedFilters ? 'HIDE' : 'REFINE'}
              </button>
            </div>
          </div>
        </div>

        <AnimatePresence>
          {showAdvancedFilters && (
            <motion.div
              initial={reduceMotion ? false : { opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={reduceMotion ? { opacity: 0 } : { opacity: 0, x: -8 }}
              transition={{ duration: reduceMotion ? 0 : 0.18, ease: tokens.motion.ease }}
              role="region"
              aria-label="Advanced queue filters"
              className="mt-phi-2 border-t border-oxford/[0.06] pt-phi-2"
            >
              <div className="grid min-w-0 gap-x-phi-6 gap-y-phi-2 md:grid-cols-3">
                <div role="group" aria-label="Attention and queue state" className="flex min-w-0 flex-col gap-phi-1">
                  <p className={`${productText.mutedLabel}`}>Attention</p>
                  <div className="flex flex-wrap gap-phi-2">
                    {ATTENTION_FILTER_CHIPS.filter((item) => item.key !== 'ALL').map(({ key: d, label }) => (
                      <AdvancedChip key={d} active={decisionFilter === d} label={label} onClick={() => setDecisionFilter(d)} />
                    ))}
                  </div>
                </div>

                <div role="group" aria-label="Partner ruling and outcome" className="flex min-w-0 flex-col gap-phi-1">
                  <p className={`${productText.mutedLabel}`}>Outcome</p>
                  <div className="flex flex-wrap gap-phi-2">
                    {RULING_FILTER_CHIPS.map(({ key: d, label }) => (
                      <AdvancedChip key={d} active={decisionFilter === d} label={label} onClick={() => setDecisionFilter(d)} />
                    ))}
                  </div>
                </div>

                <div role="group" aria-label="Reviewer signal strength" className="flex min-w-0 flex-col gap-phi-1">
                  <p className={`${productText.mutedLabel}`}>Review</p>
                  <div className="flex flex-wrap gap-phi-2">
                    {(['STRONG', 'MEDIUM', 'WEAK', 'UNREVIEWED'] as const).map((r) => (
                      <AdvancedChip key={r} active={reviewFilter === r} label={r} onClick={() => setReviewFilter(r)} />
                    ))}
                  </div>
                </div>
              </div>

              {hasActiveFilters && (
                <button type="button" onClick={resetFilters} className={`${productInteraction.action} mt-phi-2 shrink-0 !min-h-[36px]`}>
                  Reset
                </button>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </header>

      <motion.div
        key={`${sourceFilter}-${decisionFilter}-${reviewFilter}-${sortFilter}`}
        className="flex w-full min-w-0 flex-col relative [contain:layout_style]"
        initial={reduceMotion ? false : 'hidden'}
        animate="visible"
        variants={listContainerVariants}
      >
        {orderedRows.length === 0 ? (
          <div className="min-h-[18rem] px-phi-4 py-phi-7 border-t border-oxford/[0.06]">
            <div className="max-w-[32rem]">
              <p className="type-label-tab text-oxford/35">Queue view</p>
              <p className="mt-phi-3 type-body-emphasis text-oxford">No deals match this view.</p>
              <p className="mt-phi-2 type-body text-oxford/55">
                Adjust the filters or return to queue priority. Current thresholds still classify stale work after {config.thresholds.staleAfterHours} hours.
              </p>
              {hasActiveFilters && (
                <button
                  type="button"
                  onClick={resetFilters}
                  className="mt-phi-4 type-meta min-h-[44px] text-oxford/60 hover:text-oxford transition-colors"
                >
                  Reset view
                </button>
              )}
            </div>
          </div>
        ) : orderedRows.map((row, idx) => {
          const { startup } = row;
          const isSelected = selectedId === startup.id;
          const attention = getRowAttention(row);
          const isPending = row.queueState === 'pending' || row.isEscalated || row.isStale;
          const rowOpacityClass =
            row.isDecided && !isSelected ? 'opacity-[0.62] hover:opacity-100' : '';
          const rowBgClass = isSelected
            ? 'bg-oxford/[0.08]'
            : row.isDecided
              ? ''
              : row.hasHighAdverse || row.isEscalated
                ? 'bg-accent/[0.025]'
                : row.isStale
                  ? 'bg-heritageGold/[0.035]'
                  : isPending
                    ? 'bg-oxford/[0.018]'
                    : '';
          const rowHoverClass = isSelected ? '' : 'hover:bg-oxford/[0.025]';
          const metaSectorHead = (startup.scout.sector || '').split('/')[0].trim();
          const metaHasDate = Boolean(row.sortKeyValue);
          const metaHasUnresolved = Boolean(row.unresolvedAt) && !row.isDecided;
          const metaHasSector = Boolean(metaSectorHead);
          const metaHasFunding = Boolean(startup.scout.funding_stage);
          const metaHasDiligenceFlags = row.hasAdverse && !row.hasHighAdverse;
          const metaHasMonitor = row.onMonitorList;
          const metaHasLookup = row.sourceBadge === 'LOOKUP';
          const metaHasScore = showJudgmentScore(row);

          const rowAria = `${startup.scout.name}, ${startup.scout.sector ?? 'Unknown sector'}.${
            row.isDecided ? ' Decided.' : row.needsRuling ? ' Needs ruling.' : ''
          }${row.isStale && row.ageDays != null ? ` ${row.ageDays} days unresolved.` : ''}${
            row.hasAdverse ? ` ${row.adverseItems.length} adverse item${row.adverseItems.length === 1 ? '' : 's'}.` : ''
          }${
            row.onMonitorList ? ' On system monitor list.' : ''
          } Press Enter to open memo.`;

          return (
            <motion.div
              key={startup.id}
              ref={(el) => {
                if (el) rowRefs.current.set(startup.id, el);
                else rowRefs.current.delete(startup.id);
              }}
              variants={rowVariants}
              className={`group relative w-full min-w-0 border-t border-oxford/[0.07] px-phi-4 py-phi-6 cursor-pointer transition-[background-color,opacity] duration-[160ms] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 focus-visible:ring-inset ${rowHoverClass} ${rowBgClass} ${rowOpacityClass}`}
              style={{ transitionTimingFunction: 'var(--motion-ease)' }}
              onClick={() => onStartupClick(startup)}
              onKeyDown={(e) => handleRowKeyDown(e, row, idx)}
              role="button"
              tabIndex={0}
              aria-pressed={isSelected}
              aria-label={rowAria}
            >
              {(row.hasAdverse || row.isStale || row.isEscalated) && (
                <span
                  className={`absolute left-0 top-phi-4 bottom-phi-4 w-px ${
                    row.hasHighAdverse || row.isEscalated
                      ? 'bg-escalation/55'
                      : row.hasAdverse
                        ? 'bg-heritageGold/70'
                        : 'bg-oxford/18'
                  }`}
                  aria-hidden
                />
              )}
              <div className="grid grid-cols-[28px_minmax(0,1fr)] gap-x-phi-4 gap-y-phi-3 items-start">
                {/* Index */}
                <span className={`type-meta transition-colors tabular-nums pt-px sm:col-start-1 ${row.needsRuling && !row.isDecided ? 'text-oxford/45 group-hover:text-oxford/65' : 'text-oxford/25 group-hover:text-oxford/45'}`}>
                  {row.displayIndex}
                </span>

                {/* Body */}
                <div className="min-w-0 col-start-2">
                  <div className="flex min-w-0 flex-wrap items-start justify-between gap-x-phi-4 gap-y-phi-2">
                    <div className="min-w-0 flex-1">
                      <h2 className={`type-body-emphasis min-w-0 break-words ${row.isDecided ? 'text-oxford/70' : 'text-oxford'}`}>
                        {startup.scout.name}
                      </h2>
                    </div>
                    <div className="flex shrink-0 flex-wrap items-center justify-end gap-x-phi-2 gap-y-phi-1 self-start">
                      {row.reviewBand && <VerdictBandBadge band={row.reviewBand} />}
                      {(row.isEscalated || row.decisionVariant === 'escalation') && <DecisionBadge variant="escalation" />}
                      {!row.isEscalated && row.decisionVariant !== 'escalation' && <DecisionBadge variant={row.decisionVariant} />}
                    </div>
                  </div>
                  <p
                    className={`mt-phi-2 type-body-sm leading-relaxed ${
                      attention.tone === 'critical'
                        ? 'max-w-[min(100%,40rem)] text-escalation/80'
                        : row.isDecided
                          ? 'max-w-[32rem] text-oxford/42'
                          : 'max-w-[32rem] text-oxford/58'
                    }`}
                  >
                    {truncateRowReason(attention.reason)}
                  </p>
                  <div className="flex flex-wrap items-center gap-x-phi-2 gap-y-phi-1 mt-phi-3">
                    {metaHasDate && (
                      <span className="type-meta shrink-0 text-oxford/30 tabular-nums">
                        {formatRowDate(row.sortKeyValue)}
                      </span>
                    )}
                    {metaHasSector && (
                      <>
                        {metaHasDate && <span className="type-meta text-oxford/25">·</span>}
                        <span className="type-meta text-oxford/45">{metaSectorHead}</span>
                      </>
                    )}
                    {metaHasFunding && (
                      <>
                        {(metaHasDate || metaHasSector) && <span className="type-meta text-oxford/25">·</span>}
                        <span className="type-meta text-oxford/35">{startup.scout.funding_stage}</span>
                      </>
                    )}
                    {metaHasUnresolved && (
                      <>
                        {(metaHasDate || metaHasSector || metaHasFunding) && <span className="type-meta text-oxford/25">·</span>}
                        <span className="type-meta text-oxford/38 tabular-nums" title="Days this item has been unresolved">
                          Unresolved {formatUnresolvedAgeDays(row.unresolvedAt ?? '')}
                        </span>
                      </>
                    )}
                    {metaHasDiligenceFlags && (
                      <>
                        {(metaHasDate || metaHasSector || metaHasFunding || metaHasUnresolved) && (
                          <span className="type-meta text-oxford/25">·</span>
                        )}
                        <span className="type-meta text-oxford/38">
                          {row.adverseItems.length} diligence flag{row.adverseItems.length === 1 ? '' : 's'}
                        </span>
                      </>
                    )}
                    {metaHasMonitor && (
                      <>
                        {(metaHasDate || metaHasSector || metaHasFunding || metaHasUnresolved || metaHasDiligenceFlags) && (
                          <span className="type-meta text-oxford/25">·</span>
                        )}
                        <span className="type-meta text-oxford/38">On monitor</span>
                      </>
                    )}
                    {metaHasLookup && (
                      <>
                        {(metaHasDate || metaHasSector || metaHasFunding || metaHasUnresolved || metaHasDiligenceFlags || metaHasMonitor) && (
                          <span className="type-meta text-oxford/25">·</span>
                        )}
                        <span className="type-meta tracking-[0.08em] text-lookup">Lookup</span>
                      </>
                    )}
                    {metaHasScore && (
                      <>
                        {(metaHasDate ||
                          metaHasSector ||
                          metaHasFunding ||
                          metaHasUnresolved ||
                          metaHasDiligenceFlags ||
                          metaHasMonitor ||
                          metaHasLookup) && <span className="type-meta text-oxford/25">·</span>}
                        <span
                          className="type-meta tracking-[0.06em] tabular-nums text-oxford/55"
                          title="Configured weighted score"
                        >
                          {row.configuredScore}%
                        </span>
                      </>
                    )}
                  </div>
                </div>

              </div>

            </motion.div>
          );
        })}
      </motion.div>
    </div>
  );
};

function showJudgmentScore(row: WorkGridRow): boolean {
  return row.startup.review != null || row.startup.partner?.recommendation != null;
}

export default WorkGrid;
