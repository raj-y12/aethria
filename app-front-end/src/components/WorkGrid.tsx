import { useMemo, useState, useCallback, useRef, useEffect } from 'react';
import type { ReactElement, ReactNode } from 'react';
import { useSearchParams } from 'react-router';
import { LayoutGroup, motion, type Variants } from 'framer-motion';
import type { Startup } from '../types/startup';
import { tokens } from '../design-system/tokens';
import { usePrefersReducedMotion } from '../hooks';
import EmptyState from './EmptyState';
import DecisionQueueHeader, {
  type FlagFilter,
  type OutcomeFilter,
  type QueueView,
  type ReviewFilter,
  type SortFilter,
  type SourceFilter,
} from './queue/DecisionQueueHeader';
import DocketCaseRow from './queue/DocketCaseRow';
import type { DocketRowModel } from './queue/queueRowShared';
import { normalizeQuery, startupMatchesQuery } from '../lib/queueSearch';
import { getDecisionBadgeVariant } from '../lib/decisionBadgeVariant';
import { queueAttentionRank } from '../lib/dealState';
import {
  computeConfiguredScore,
  createDefaultFundConfiguration,
  type FundConfiguration,
} from '../lib/fundConfiguration';
import { productInteraction } from '../design-system/productSystem';
import {
  buildQueueRowContext,
  getVisibleRecommendation,
  resolveQueueAttentionDriver,
  rowSectorStageLine,
} from '../lib/queueAttentionDriver';

interface WorkGridProps {
  startups: Startup[];
  onStartupClick: (startup: Startup) => void;
  selectedId?: string | null;
  watchlistIds?: Set<string>;
  fundConfiguration?: FundConfiguration;
  /** Controlled queue view — the room header readouts own view switching. */
  queueView: QueueView;
  onQueueViewChange: (view: QueueView) => void;
  /** Reports per-view row counts so the room header readouts stay live. */
  onViewCounts?: (counts: Record<QueueView, number>) => void;
  /** AppFrame releases the initial cascade after a bare-to-full chrome entrance. */
  entranceReady?: boolean;
  /** Queue views, rendered into the docket's control line by the owning room. */
  viewsSlot?: ReactNode;
}

const EMPTY_WATCHLIST_IDS = new Set<string>();

// Docket sort/filter is a view preference, not tenant data — persisted
// unscoped across accounts on the same browser, like a UI zoom level.
const DOCKET_PREFS_KEY = 'aethria.docket.prefs.v1';

interface DocketPrefs {
  sortFilter: SortFilter;
  sourceFilters: SourceFilter[];
  outcomeFilters: OutcomeFilter[];
  flagFilters: FlagFilter[];
  reviewFilters: ReviewFilter[];
}

function loadDocketPrefs(): Partial<DocketPrefs> {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(DOCKET_PREFS_KEY);
    return raw ? (JSON.parse(raw) as Partial<DocketPrefs>) : {};
  } catch {
    return {};
  }
}

function toggleInSet<T>(prev: Set<T>, value: T): Set<T> {
  const next = new Set(prev);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}

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
  watchlistSet: Set<string>
): DocketRowModel {
  const configuredScore = computeConfiguredScore(startup, config);
  const queueContext = buildQueueRowContext(startup, config, {
    configuredScore,
    onMonitorList: watchlistSet.has(startup.id),
  });
  const attentionDriver = resolveQueueAttentionDriver(queueContext);
  return {
    startup,
    sourceBadge: getSourceBadge(startup),
    hasReview: startup.review != null,
    decisionVariant: getDecisionBadgeVariant(startup),
    queueContext,
    attentionDriver,
    sectorStage: rowSectorStageLine(startup),
    sortKeyValue: sortKey(startup),
    unresolvedAt: getUnresolvedAt(startup),
    firstSeenAt: startup.timestamps?.first_seen_at ?? startup.timestamps?.discovered_at ?? '',
    hasHighAdverse: queueContext.adverseItems.some((item) => item.severity === 'high'),
    isNewToUser: Boolean(startup.is_new_to_user),
  };
}

// Multi-select matchers — selected chips within a group are OR'd. An empty set
// means the group imposes no constraint.
function rowMatchesOutcomeFilters(row: DocketRowModel, filters: Set<OutcomeFilter>): boolean {
  if (filters.size === 0) return true;
  const rec = getVisibleRecommendation(row.startup);
  for (const f of filters) {
    if (f === 'YES' && rec === 'INVEST') return true;
    if (f === 'NO' && rec === 'PASS') return true;
    if (f === 'MAYBE' && rec === 'MONITOR') return true;
    if (f === 'DECIDED' && row.queueContext.isDecided) return true;
  }
  return false;
}

function rowMatchesFlagFilters(row: DocketRowModel, filters: Set<FlagFilter>): boolean {
  if (filters.size === 0) return true;
  for (const f of filters) {
    if (f === 'ADVERSE' && !row.queueContext.isDecided && row.hasHighAdverse) return true;
  }
  return false;
}

function rowMatchesReviewFilters(row: DocketRowModel, filters: Set<ReviewFilter>): boolean {
  if (filters.size === 0) return true;
  for (const f of filters) {
    if (f === 'UNREVIEWED' && row.startup.review == null) return true;
    if (f === 'REVIEWED' && row.hasReview) return true;
    if (f === 'UNREVIEWED' && !row.hasReview) return true;
  }
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

const WorkGrid = ({
  startups,
  onStartupClick,
  selectedId,
  watchlistIds,
  fundConfiguration,
  queueView,
  onQueueViewChange,
  onViewCounts,
  entranceReady = true,
  viewsSlot,
}: WorkGridProps): ReactElement => {
  const watchlistSet = watchlistIds ?? EMPTY_WATCHLIST_IDS;
  const config = fundConfiguration ?? createDefaultFundConfiguration();
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
    if (next) onQueueViewChange(next);
    const params = new URLSearchParams(searchParams);
    params.delete('queue');
    setSearchParams(params, { replace: true });
  }, [searchParams, setSearchParams, onQueueViewChange]);
  const [sourceFilters, setSourceFilters] = useState<Set<SourceFilter>>(
    () => new Set(loadDocketPrefs().sourceFilters ?? [])
  );
  const [outcomeFilters, setOutcomeFilters] = useState<Set<OutcomeFilter>>(
    () => new Set(loadDocketPrefs().outcomeFilters ?? [])
  );
  const [flagFilters, setFlagFilters] = useState<Set<FlagFilter>>(
    () => new Set(loadDocketPrefs().flagFilters ?? [])
  );
  const [reviewFilters, setReviewFilters] = useState<Set<ReviewFilter>>(
    () => new Set(loadDocketPrefs().reviewFilters ?? [])
  );
  const [sortFilter, setSortFilter] = useState<SortFilter>(
    () => loadDocketPrefs().sortFilter ?? 'QUEUE_PRIORITY'
  );
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [query, setQuery] = useState('');
  // In the NEW view, a clicked row is acknowledged and would normally drop out
  // immediately (is_new_to_user flips false). Pin it so it stays visible until
  // the analyst clicks off it (closes the memo or selects another row).
  const [pinnedNewId, setPinnedNewId] = useState<string | null>(null);
  const reduceMotion = usePrefersReducedMotion();
  const hasActiveFilters =
    sourceFilters.size > 0 ||
    outcomeFilters.size > 0 ||
    flagFilters.size > 0 ||
    reviewFilters.size > 0 ||
    sortFilter !== 'QUEUE_PRIORITY';

  const toggleSource = useCallback(
    (f: SourceFilter) => setSourceFilters((prev) => toggleInSet(prev, f)),
    []
  );
  const toggleOutcome = useCallback(
    (f: OutcomeFilter) => setOutcomeFilters((prev) => toggleInSet(prev, f)),
    []
  );
  const toggleFlag = useCallback(
    (f: FlagFilter) => setFlagFilters((prev) => toggleInSet(prev, f)),
    []
  );
  const toggleReview = useCallback(
    (f: ReviewFilter) => setReviewFilters((prev) => toggleInSet(prev, f)),
    []
  );

  const resetFilters = useCallback(() => {
    setSourceFilters(new Set());
    setOutcomeFilters(new Set());
    setFlagFilters(new Set());
    setReviewFilters(new Set());
    setSortFilter('QUEUE_PRIORITY');
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const prefs: DocketPrefs = {
        sortFilter,
        sourceFilters: [...sourceFilters],
        outcomeFilters: [...outcomeFilters],
        flagFilters: [...flagFilters],
        reviewFilters: [...reviewFilters],
      };
      window.localStorage.setItem(DOCKET_PREFS_KEY, JSON.stringify(prefs));
    } catch {
      // Best-effort — quota or private-mode failures just skip persistence.
    }
  }, [sortFilter, sourceFilters, outcomeFilters, flagFilters, reviewFilters]);

  const listContainerVariants = useMemo((): Variants | undefined =>
    reduceMotion
      ? undefined
      : {
          hidden: {},
          visible: { transition: { staggerChildren: 0.026, delayChildren: 0.02 } },
        },
    [reduceMotion]
  );

  const rowVariants = useMemo((): Variants | undefined =>
    reduceMotion
      ? undefined
      : {
          hidden: { opacity: 0, transform: 'translateY(3px)' },
          visible: {
            opacity: 1,
            transform: 'translateY(0px)',
            transition: { duration: 0.18, ease: tokens.motion.ease },
          },
        },
    [reduceMotion]
  );

  const emptyStateContainerVariants = useMemo((): Variants | undefined =>
    reduceMotion
      ? undefined
      : {
          hidden: {},
          visible: { transition: { staggerChildren: 0.05, delayChildren: 0.03 } },
        },
    [reduceMotion]
  );

  const emptyStateItemVariants = useMemo((): Variants | undefined =>
    reduceMotion
      ? undefined
      : {
          hidden: { opacity: 0, transform: 'translateY(8px)' },
          visible: {
            opacity: 1,
            transform: 'translateY(0px)',
            transition: { duration: 0.35, ease: tokens.motion.ease },
          },
        },
    [reduceMotion]
  );

  const rowRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  const allModels = useMemo(() => {
    return startups.map((startup) => buildDocketRow(startup, config, watchlistSet));
  }, [startups, config, watchlistSet]);

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

  useEffect(() => {
    onViewCounts?.(viewCounts);
  }, [viewCounts, onViewCounts]);

  const orderedModels = useMemo(() => {
    // A search is a retrieval, not a refinement: it looks across the whole
    // docket, because the operator recalling a name does not also recall which
    // view it is sitting in.
    const normalizedQuery = normalizeQuery(query);
    const filtered = allModels.filter((row) => {
      if (normalizedQuery) {
        if (!startupMatchesQuery(row.startup, normalizedQuery)) return false;
      } else {
        const pinnedInNew =
          queueView === 'NEW' && pinnedNewId != null && row.startup.id === pinnedNewId;
        if (!pinnedInNew && !rowMatchesQueueView(row, queueView)) return false;
      }
      if (sourceFilters.size > 0 && !sourceFilters.has(row.sourceBadge)) return false;
      if (!rowMatchesOutcomeFilters(row, outcomeFilters)) return false;
      if (!rowMatchesFlagFilters(row, flagFilters)) return false;
      if (!rowMatchesReviewFilters(row, reviewFilters)) return false;
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
  }, [allModels, queueView, query, sourceFilters, outcomeFilters, flagFilters, reviewFilters, sortFilter, pinnedNewId]);

  // Drop the pin once the selection moves off the pinned row (memo closed or
  // a different row selected), letting the acknowledged row leave the NEW view.
  useEffect(() => {
    if (pinnedNewId && selectedId !== pinnedNewId) setPinnedNewId(null);
  }, [selectedId, pinnedNewId]);

  const handleRowSelect = useCallback(
    (startup: Startup) => {
      if (queueView === 'NEW') setPinnedNewId(startup.id);
      onStartupClick(startup);
    },
    [queueView, onStartupClick]
  );

  // Arrow-key roving focus is handled here; Enter/Space activation is bound
  // at the row call site because docket rows use a button role.
  const handleRowKeyDown = useCallback(
    (e: React.KeyboardEvent, idx: number) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        const next = orderedModels[idx + 1];
        if (next) rowRefs.current.get(next.startup.id)?.focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const prev = orderedModels[idx - 1];
        if (prev) rowRefs.current.get(prev.startup.id)?.focus();
      }
    },
    [orderedModels]
  );

  if (startups.length === 0) {
    return (
      <div className="w-full h-full min-h-[12rem] flex flex-col items-center justify-center">
        <EmptyState
          label="Docket"
          body="Scouts are searching against your mandate. New matters appear here as they land."
        />
      </div>
    );
  }

  return (
    <div className="aethria-queue-surface w-full font-sans bg-surface-canvas selection:bg-oxford selection:text-paper">
      <DecisionQueueHeader
        config={config}
        sortFilter={sortFilter}
        onSortFilterChange={setSortFilter}
        query={query}
        onQueryChange={setQuery}
        sourceFilters={sourceFilters}
        onToggleSource={toggleSource}
        outcomeFilters={outcomeFilters}
        onToggleOutcome={toggleOutcome}
        flagFilters={flagFilters}
        onToggleFlag={toggleFlag}
        reviewFilters={reviewFilters}
        onToggleReview={toggleReview}
        showAdvancedFilters={showAdvancedFilters}
        onToggleAdvancedFilters={() => setShowAdvancedFilters((v) => !v)}
        hasActiveFilters={hasActiveFilters}
        activeFilterCount={
          sourceFilters.size + outcomeFilters.size + flagFilters.size + reviewFilters.size
        }
        onResetFilters={resetFilters}
        reduceMotion={reduceMotion}
        viewsSlot={viewsSlot}
      />

      <LayoutGroup id="decision-queue">
        {orderedModels.length === 0 ? (
          <div className="aethria-queue-list flex w-full min-w-0 flex-col relative [contain:layout_style] py-phi-1 pb-phi-6">
            <div className="min-h-[16rem] py-phi-5">
              <motion.div
                key={`${queueView}-${[...sourceFilters].join(',')}-${[...outcomeFilters].join(',')}-${[...flagFilters].join(',')}-${[...reviewFilters].join(',')}-${sortFilter}`}
                className="max-w-[32rem]"
                initial={reduceMotion ? false : 'hidden'}
                animate={reduceMotion || entranceReady ? 'visible' : 'hidden'}
                variants={emptyStateContainerVariants}
              >
                <motion.p className="type-label-tab text-oxford/65" variants={emptyStateItemVariants}>
                  {query.trim() ? 'Search' : 'Queue view'}
                </motion.p>
                <motion.p
                  className="mt-phi-3 type-body-emphasis text-oxford"
                  variants={emptyStateItemVariants}
                >
                  {query.trim()
                    ? `Nothing on the docket matches “${query.trim()}”.`
                    : 'No deals match this view.'}
                </motion.p>
                <motion.p className="mt-phi-2 type-body text-oxford/65" variants={emptyStateItemVariants}>
                  {query.trim()
                    ? 'This searches every company already on the docket. To bring in one Aethria has not seen, dispatch a lookup.'
                    : `Clear filters or switch to a broader queue view. Stale work is classified after ${config.thresholds.staleAfterHours} hours.`}
                </motion.p>
                {(hasActiveFilters || (queueView !== 'PRIORITY' && queueView !== 'ALL')) && (
                  <motion.div
                    className="mt-phi-4 flex flex-wrap items-center gap-x-phi-4 gap-y-phi-1"
                    role="group"
                    aria-label="Queue empty-state actions"
                    variants={emptyStateItemVariants}
                  >
                    {hasActiveFilters && (
                      <button
                        type="button"
                        onClick={resetFilters}
                        className={`${productInteraction.action} type-action-strong btn-interaction btn-interaction--no-press`}
                      >
                        Clear filters
                      </button>
                    )}
                    {queueView !== 'PRIORITY' && queueView !== 'ALL' && (
                      <>
                        <button
                          type="button"
                          onClick={() => onQueueViewChange('PRIORITY')}
                          aria-label="Switch to priority queue view"
                          className={`${productInteraction.action} type-action-strong btn-interaction btn-interaction--no-press`}
                        >
                          Show priority queue
                        </button>
                        <button
                          type="button"
                          onClick={() => onQueueViewChange('ALL')}
                          aria-label="Switch to all deals view"
                          className={`${productInteraction.action} btn-interaction btn-interaction--no-press`}
                        >
                          Show all deals
                        </button>
                      </>
                    )}
                  </motion.div>
                )}
              </motion.div>
            </div>
          </div>
        ) : (
          <motion.div
            key={`${queueView}-${[...sourceFilters].join(',')}-${[...outcomeFilters].join(',')}-${[...flagFilters].join(',')}-${[...reviewFilters].join(',')}-${sortFilter}`}
            className="aethria-queue-list relative flex w-full min-w-0 flex-col pt-phi-2 pb-phi-5 [contain:layout_style]"
            initial={reduceMotion ? false : 'hidden'}
            animate={reduceMotion || entranceReady ? 'visible' : 'hidden'}
            variants={listContainerVariants}
          >
            {orderedModels.map((model, idx) => {
              const isSelected = selectedId === model.startup.id;
              const keyDown = (e: React.KeyboardEvent) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleRowSelect(model.startup);
                  return;
                }
                handleRowKeyDown(e, idx);
              };

              return (
                <motion.div
                  key={model.startup.id}
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
                    onClick={() => handleRowSelect(model.startup)}
                    onKeyDown={keyDown}
                    badges={config.verdictBadges}
                  />
                </motion.div>
              );
            })}
          </motion.div>
        )}
      </LayoutGroup>
    </div>
  );
};

export default WorkGrid;
