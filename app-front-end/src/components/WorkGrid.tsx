import { useMemo, useState, useCallback, useRef, useEffect } from 'react';
import { useSearchParams } from 'react-router';
import { LayoutGroup, motion, type Variants } from 'framer-motion';
import type { Startup } from '../types/startup';
import { getReviewerQualityBand } from '../design-system/semantics';
import { tokens } from '../design-system/tokens';
import { usePrefersReducedMotion } from '../hooks';
import EmptyState from './EmptyState';
import DecisionQueueHeader, {
  type DecisionFilter,
  type QueueView,
  type ReviewFilter,
  type SortFilter,
  type SourceFilter,
} from './queue/DecisionQueueHeader';
import DocketCaseRow from './queue/DocketCaseRow';
import type { DocketRowModel } from './queue/queueRowShared';
import { getDecisionBadgeVariant } from '../lib/decisionBadgeVariant';
import { queueAttentionRank } from '../lib/dealState';
import {
  computeConfiguredScore,
  createDefaultFundConfiguration,
  type FundConfiguration,
} from '../lib/fundConfiguration';
import { QUEUE_ROW_LAYOUT_TRANSITION } from './queue/queueRowMotion';
import {
  buildQueueRowContext,
  getVisibleRecommendation,
  resolveQueueAttentionDriver,
  rowQueueOneLiner,
  rowSectorStageLine,
} from '../lib/queueAttentionDriver';

interface WorkGridProps {
  startups: Startup[];
  onStartupClick: (startup: Startup) => void;
  selectedId?: string | null;
  watchlistIds?: Set<string>;
  fundConfiguration?: FundConfiguration;
}

const EMPTY_WATCHLIST_IDS = new Set<string>();

function sortKey(s: Startup): string {
  return s.timestamps?.partnered_at ?? s.timestamps?.reviewed_at ?? s.timestamps?.discovered_at ?? '';
}

function getSourceBadge(startup: Startup): 'LOOKUP' | 'SCOUT' {
  const origin = (startup.scout.origin_type ?? '').toLowerCase();
  return origin === 'on_demand_lookup' || Boolean(startup.scout.lookup_id || startup.scout.lookup_query)
    ? 'LOOKUP'
    : 'SCOUT';
}

function getUnresolvedAt(startup: Startup): string | null {
  return startup.unresolved_at ?? startup.timestamps?.unresolved_at ?? null;
}

function buildDocketRow(
  startup: Startup,
  config: FundConfiguration,
  watchlistSet: Set<string>,
  displayIndex: string
): DocketRowModel {
  const configuredScore = computeConfiguredScore(startup, config);
  const queueContext = buildQueueRowContext(startup, config, {
    configuredScore,
    onMonitorList: watchlistSet.has(startup.id),
  });
  const attentionDriver = resolveQueueAttentionDriver(queueContext);
  return {
    startup,
    displayIndex,
    sourceBadge: getSourceBadge(startup),
    reviewBand: getReviewerQualityBand(startup.review),
    decisionVariant: getDecisionBadgeVariant(startup),
    queueContext,
    attentionDriver,
    oneLiner: rowQueueOneLiner(queueContext, attentionDriver),
    sectorStage: rowSectorStageLine(startup),
    sortKeyValue: sortKey(startup),
    unresolvedAt: getUnresolvedAt(startup),
    firstSeenAt: startup.timestamps?.first_seen_at ?? startup.timestamps?.discovered_at ?? '',
    hasHighAdverse: queueContext.adverseItems.some((item) => item.severity === 'high'),
    isNewToUser: Boolean(startup.is_new_to_user),
  };
}

function rowMatchesDecisionFilter(row: DocketRowModel, filter: DecisionFilter): boolean {
  if (filter === 'ALL') return true;
  const visibleRecommendation = getVisibleRecommendation(row.startup);
  const { queueContext, decisionVariant } = row;
  const onMonitorList = queueContext.onMonitorList;
  if (filter === 'WATCHLIST') return onMonitorList || visibleRecommendation === 'MONITOR';
  if (filter === 'NEEDS_RULING') return queueContext.needsRuling;
  if (filter === 'STALE') return queueContext.isStale;
  if (filter === 'ADVERSE') return !queueContext.isDecided && row.hasHighAdverse;
  if (filter === 'ESCALATION') {
    return !queueContext.isDecided && (queueContext.isEscalated || decisionVariant === 'escalation');
  }
  if (filter === 'DECIDED') return queueContext.isDecided;
  if (filter === 'AWAITING_REVIEW') return !row.startup.review && !queueContext.isDecided;
  if (filter === 'YES') return visibleRecommendation === 'INVEST';
  if (filter === 'NO') return visibleRecommendation === 'PASS';
  if (filter === 'MAYBE') return visibleRecommendation === 'MONITOR';
  return false;
}

function rowMatchesQueueView(row: DocketRowModel, view: QueueView): boolean {
  if (view === 'ALL' || view === 'PRIORITY') return true;
  if (view === 'NEW') return row.isNewToUser;
  if (view === 'STALE') return row.queueContext.isStale;
  if (view === 'ESCALATED') return !row.queueContext.isDecided && row.queueContext.isEscalated;
  return false;
}

function priorityRank(row: DocketRowModel): number {
  const { queueContext, hasHighAdverse } = row;
  if (queueContext.isDecided) return 4;
  if (hasHighAdverse || queueContext.isEscalated) return 0;
  if (queueContext.isStale) return 1;
  if (row.startup.review) return 2;
  return queueAttentionRank(row.startup);
}

const WorkGrid = ({ startups, onStartupClick, selectedId, watchlistIds, fundConfiguration }: WorkGridProps): JSX.Element => {
  const watchlistSet = watchlistIds ?? EMPTY_WATCHLIST_IDS;
  const config = fundConfiguration ?? createDefaultFundConfiguration();
  const [queueView, setQueueView] = useState<QueueView>('PRIORITY');
  const [searchParams, setSearchParams] = useSearchParams();
  // Deep-link from the rail attention cluster: ?queue=new|escalated|priority|stale.
  useEffect(() => {
    const q = searchParams.get('queue');
    if (!q) return;
    const map: Record<string, QueueView> = {
      new: 'NEW',
      escalated: 'ESCALATED',
      priority: 'PRIORITY',
      stale: 'STALE',
      all: 'ALL',
    };
    const next = map[q.toLowerCase()];
    if (next) setQueueView(next);
    const params = new URLSearchParams(searchParams);
    params.delete('queue');
    setSearchParams(params, { replace: true });
  }, [searchParams, setSearchParams]);
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
          visible: { transition: { staggerChildren: 0.04, delayChildren: 0.04 } },
        },
    [reduceMotion]
  );

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

  const rowRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  const stableIndex = useMemo(() => {
    const byDiscovery = [...startups].sort((a, b) => sortKey(a).localeCompare(sortKey(b)));
    return new Map(byDiscovery.map((s, i) => [s.id, (i + 1).toString().padStart(2, '0')]));
  }, [startups]);

  const allModels = useMemo(() => {
    return startups.map((startup) =>
      buildDocketRow(startup, config, watchlistSet, stableIndex.get(startup.id) ?? '00')
    );
  }, [startups, config, watchlistSet, stableIndex]);

  const viewCounts = useMemo(
    (): Record<QueueView, number> => ({
      ALL: allModels.length,
      PRIORITY: allModels.length,
      NEW: allModels.filter((r) => r.isNewToUser).length,
      STALE: allModels.filter((r) => r.queueContext.isStale).length,
      ESCALATED: allModels.filter((r) => !r.queueContext.isDecided && r.queueContext.isEscalated).length,
    }),
    [allModels]
  );

  const orderedModels = useMemo(() => {
    const filtered = allModels.filter((row) => {
      if (!rowMatchesQueueView(row, queueView)) return false;
      if (sourceFilter === 'LOOKUP' && row.sourceBadge !== 'LOOKUP') return false;
      if (sourceFilter === 'SCOUT' && row.sourceBadge !== 'SCOUT') return false;
      if (!rowMatchesDecisionFilter(row, decisionFilter)) return false;
      if (reviewFilter === 'UNREVIEWED' && row.startup.review != null) return false;
      if (reviewFilter !== 'ALL' && reviewFilter !== 'UNREVIEWED' && row.reviewBand !== reviewFilter) {
        return false;
      }
      return true;
    });
    const sorted = [...filtered];
    if (sortFilter === 'QUEUE_PRIORITY') {
      if (queueView === 'NEW') {
        sorted.sort((a, b) => b.firstSeenAt.localeCompare(a.firstSeenAt));
      } else if (queueView === 'STALE') {
        sorted.sort((a, b) => (a.unresolvedAt ?? '9999').localeCompare(b.unresolvedAt ?? '9999'));
      } else if (queueView === 'ALL') {
        sorted.sort((a, b) => b.sortKeyValue.localeCompare(a.sortKeyValue));
      } else {
        sorted.sort((a, b) => {
          const ar = priorityRank(a);
          const br = priorityRank(b);
          if (ar !== br) return ar - br;
          return b.sortKeyValue.localeCompare(a.sortKeyValue);
        });
      }
    } else {
      switch (sortFilter) {
        case 'OLDEST':
          sorted.sort((a, b) => a.sortKeyValue.localeCompare(b.sortKeyValue));
          break;
        case 'UNRESOLVED_OLDEST':
          sorted.sort((a, b) => (a.unresolvedAt ?? '9999').localeCompare(b.unresolvedAt ?? '9999'));
          break;
        case 'NEWEST':
        default:
          sorted.sort((a, b) => b.sortKeyValue.localeCompare(a.sortKeyValue));
          break;
      }
    }
    return sorted;
  }, [allModels, queueView, sourceFilter, decisionFilter, reviewFilter, sortFilter]);

  const handleRowKeyDown = useCallback(
    (e: React.KeyboardEvent, model: DocketRowModel, idx: number) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onStartupClick(model.startup);
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        const next = orderedModels[idx + 1];
        if (next) rowRefs.current.get(next.startup.id)?.focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const prev = orderedModels[idx - 1];
        if (prev) rowRefs.current.get(prev.startup.id)?.focus();
      }
    },
    [onStartupClick, orderedModels]
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
    <div className="aethria-queue-surface w-full font-sans bg-surface-canvas selection:bg-oxford selection:text-paper">
      <DecisionQueueHeader
        config={config}
        queueView={queueView}
        onQueueViewChange={setQueueView}
        viewCounts={viewCounts}
        sortFilter={sortFilter}
        onSortFilterChange={setSortFilter}
        sourceFilter={sourceFilter}
        onSourceFilterChange={setSourceFilter}
        decisionFilter={decisionFilter}
        onDecisionFilterChange={setDecisionFilter}
        reviewFilter={reviewFilter}
        onReviewFilterChange={setReviewFilter}
        showAdvancedFilters={showAdvancedFilters}
        onToggleAdvancedFilters={() => setShowAdvancedFilters((v) => !v)}
        hasActiveFilters={hasActiveFilters}
        onResetFilters={resetFilters}
        reduceMotion={reduceMotion}
      />

      <LayoutGroup id="decision-queue">
      <motion.div
        key={`${queueView}-${sourceFilter}-${decisionFilter}-${reviewFilter}-${sortFilter}`}
        className="aethria-queue-list flex w-full min-w-0 flex-col relative [contain:layout_style] py-phi-1"
        initial={reduceMotion ? false : 'hidden'}
        animate="visible"
        variants={listContainerVariants}
      >
        {orderedModels.length === 0 ? (
          <div className="min-h-[16rem] px-phi-4 py-phi-5">
            <div className="max-w-[32rem]">
              <p className="type-label-tab text-oxford/35">Queue view</p>
              <p className="mt-phi-3 type-body-emphasis text-oxford">No deals match this view.</p>
              <p className="mt-phi-2 type-body text-oxford/55">
                Adjust filters or return to priority. Stale work is classified after {config.thresholds.staleAfterHours}{' '}
                hours.
              </p>
              {(hasActiveFilters || (queueView !== 'PRIORITY' && queueView !== 'ALL')) && (
                <div className="mt-phi-4 flex flex-wrap items-center gap-x-phi-4">
                  {hasActiveFilters && (
                    <button
                      type="button"
                      onClick={resetFilters}
                      className="type-meta min-h-[44px] text-oxford/60 hover:text-oxford transition-colors"
                    >
                      Reset filters
                    </button>
                  )}
                  {queueView !== 'PRIORITY' && queueView !== 'ALL' && (
                    <button
                      type="button"
                      onClick={() => setQueueView('PRIORITY')}
                      className="type-meta min-h-[44px] text-oxford/60 hover:text-oxford transition-colors"
                    >
                      Priority view
                    </button>
                  )}
                  {queueView !== 'ALL' && queueView !== 'PRIORITY' && (
                    <button
                      type="button"
                      onClick={() => setQueueView('ALL')}
                      className="type-meta min-h-[44px] text-oxford/60 hover:text-oxford transition-colors"
                    >
                      All deals
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        ) : (
          orderedModels.map((model, idx) => {
            const isSelected = selectedId === model.startup.id;
            const keyDown = (e: React.KeyboardEvent) => handleRowKeyDown(e, model, idx);

            return (
              <motion.div
                key={model.startup.id}
                layout={!reduceMotion}
                transition={reduceMotion ? undefined : QUEUE_ROW_LAYOUT_TRANSITION}
                variants={rowVariants}
                className="min-w-0"
              >
                <DocketCaseRow
                  ref={(el) => {
                    if (el) rowRefs.current.set(model.startup.id, el);
                    else rowRefs.current.delete(model.startup.id);
                  }}
                  model={model}
                  isSelected={isSelected}
                  rowIndex={idx}
                  onClick={() => onStartupClick(model.startup)}
                  onKeyDown={keyDown}
                  badges={config.verdictBadges}
                />
              </motion.div>
            );
          })
        )}
      </motion.div>
      </LayoutGroup>
    </div>
  );
};

export default WorkGrid;
