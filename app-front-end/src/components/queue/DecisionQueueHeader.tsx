import { AnimatePresence, motion } from 'framer-motion';
import { tokens } from '../../design-system/tokens';
import { productInteraction, productPanel, productText } from '../../design-system/productSystem';
import type { FundConfiguration } from '../../lib/fundConfiguration';

export type QueueView = 'ALL' | 'PRIORITY' | 'NEW' | 'STALE' | 'ESCALATED';

// Multi-select filter groups. An empty set means "no constraint" (show all).
// Within a group the selected chips are OR'd; across groups they are AND'd.
export type SourceFilter = 'SCOUT' | 'LOOKUP';

export type OutcomeFilter = 'YES' | 'NO' | 'MAYBE' | 'DECIDED';

export type FlagFilter = 'ADVERSE';

export type ReviewFilter = 'STRONG' | 'MEDIUM' | 'WEAK' | 'UNREVIEWED';

export type SortFilter = 'QUEUE_PRIORITY' | 'NEWEST' | 'OLDEST' | 'UNRESOLVED_OLDEST';

const QUEUE_VIEW_LABELS: { key: QueueView; label: string }[] = [
  { key: 'ALL', label: 'All' },
  { key: 'PRIORITY', label: 'Priority' },
  { key: 'NEW', label: 'New' },
  { key: 'STALE', label: 'Stale' },
  { key: 'ESCALATED', label: 'Escalated' },
];

const SORT_OPTIONS: { value: SortFilter; label: string; title: string }[] = [
  { value: 'QUEUE_PRIORITY', label: '↕', title: 'Queue order' },
  { value: 'NEWEST', label: '↓', title: 'Newest first' },
  { value: 'OLDEST', label: '↑', title: 'Oldest first' },
  { value: 'UNRESOLVED_OLDEST', label: '↥', title: 'Longest unresolved' },
];

const SOURCE_FILTER_CHIPS: { key: SourceFilter; label: string }[] = [
  { key: 'SCOUT', label: 'SCOUT' },
  { key: 'LOOKUP', label: 'LOOKUP' },
];

const OUTCOME_FILTER_CHIPS: { key: OutcomeFilter; label: string }[] = [
  { key: 'YES', label: 'INVEST' },
  { key: 'MAYBE', label: 'MONITOR' },
  { key: 'NO', label: 'PASS' },
  { key: 'DECIDED', label: 'ANY DECIDED' },
];

const FLAG_FILTER_CHIPS: { key: FlagFilter; label: string }[] = [
  { key: 'ADVERSE', label: 'ADVERSE' },
];

const REVIEW_FILTER_CHIPS: { key: ReviewFilter; label: string }[] = [
  { key: 'STRONG', label: 'STRONG' },
  { key: 'MEDIUM', label: 'MEDIUM' },
  { key: 'WEAK', label: 'WEAK' },
  { key: 'UNREVIEWED', label: 'UNREVIEWED' },
];

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
      className={`type-meta text-[10px] min-h-[36px] whitespace-nowrap px-[40px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 ${
        active ? 'bg-oxford text-paper' : 'bg-oxford/[0.035] hover:bg-oxford/[0.065] text-oxford/[0.58]'
      }`}
    >
      {label}
    </button>
  );
}

function QueueTab({
  active,
  label,
  count,
  onClick,
  emphasize = false,
  reduceMotion = false,
}: {
  active: boolean;
  label: string;
  count?: number;
  onClick: () => void;
  emphasize?: boolean;
  reduceMotion?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`type-meta min-h-[36px] px-phi-3 transition-colors btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 ${
        emphasize
          ? active
            ? 'rounded-none bg-oxford text-paper'
            : 'rounded-none bg-oxford/[0.07] text-oxford hover:bg-oxford/[0.11]'
          : active
            ? 'text-oxford font-semibold'
            : 'text-oxford/40 hover:text-oxford/70'
      } uppercase tracking-[0.12em]`}
    >
      {label}
      {count != null ? (
        <motion.span
          className={`ml-phi-1 inline-flex min-w-[1.5rem] items-center justify-center tabular-nums ${
            emphasize
              ? active
                ? 'text-paper'
                : 'rounded-none bg-paper px-phi-1 text-oxford'
              : active
                ? 'text-oxford/55'
                : 'text-oxford/[0.28]'
          }`}
          initial={reduceMotion || !emphasize ? false : { scale: 0.92, opacity: 0.9 }}
          animate={reduceMotion || !emphasize ? undefined : { scale: [0.92, 1.08, 1], opacity: [0.9, 1, 1] }}
          transition={reduceMotion || !emphasize ? undefined : { duration: 0.42, ease: tokens.motion.ease }}
        >
          {count}
        </motion.span>
      ) : null}
    </button>
  );
}

export interface DecisionQueueHeaderProps {
  config: FundConfiguration;
  queueView: QueueView;
  onQueueViewChange: (view: QueueView) => void;
  viewCounts: Record<QueueView, number>;
  sortFilter: SortFilter;
  onSortFilterChange: (sort: SortFilter) => void;
  sourceFilters: Set<SourceFilter>;
  onToggleSource: (filter: SourceFilter) => void;
  outcomeFilters: Set<OutcomeFilter>;
  onToggleOutcome: (filter: OutcomeFilter) => void;
  flagFilters: Set<FlagFilter>;
  onToggleFlag: (filter: FlagFilter) => void;
  reviewFilters: Set<ReviewFilter>;
  onToggleReview: (filter: ReviewFilter) => void;
  showAdvancedFilters: boolean;
  onToggleAdvancedFilters: () => void;
  hasActiveFilters: boolean;
  onResetFilters: () => void;
  reduceMotion: boolean;
}

export default function DecisionQueueHeader({
  config,
  queueView,
  onQueueViewChange,
  viewCounts,
  sortFilter,
  onSortFilterChange,
  sourceFilters,
  onToggleSource,
  outcomeFilters,
  onToggleOutcome,
  flagFilters,
  onToggleFlag,
  reviewFilters,
  onToggleReview,
  showAdvancedFilters,
  onToggleAdvancedFilters,
  hasActiveFilters,
  onResetFilters,
  reduceMotion,
}: DecisionQueueHeaderProps) {
  return (
    <header
      className={`sticky top-0 z-20 ${productPanel.header} !px-phi-0`}
    >
      <div className="flex min-w-0 flex-col gap-phi-2">
        <p
          className={productText.mutedLabel}
          title={`${config.thresholds.staleAfterHours}h stale · ${config.risk.sensitivity} risk`}
        >
          Decision queue
        </p>

        <div className="flex min-w-0 flex-wrap items-center gap-x-phi-3 gap-y-phi-1">
          <div className="flex items-center gap-0" role="group" aria-label="Queue views">
            {QUEUE_VIEW_LABELS.map(({ key, label }) => (
              <QueueTab
                key={key}
                active={queueView === key}
                label={label}
                count={
                  key === 'ALL'
                    ? viewCounts.ALL
                    : key === 'NEW' && viewCounts.NEW > 0
                      ? viewCounts.NEW
                      : undefined
                }
                emphasize={key === 'NEW' && viewCounts.NEW > 0}
                reduceMotion={reduceMotion}
                onClick={() => onQueueViewChange(key)}
              />
            ))}
          </div>

          <div className="ml-auto flex items-center gap-x-phi-2">
            <div className="relative shrink-0">
              <select
                value={sortFilter}
                onChange={(e) => onSortFilterChange(e.target.value as SortFilter)}
                aria-label={SORT_OPTIONS.find((o) => o.value === sortFilter)?.title ?? 'Sort deals'}
                title={SORT_OPTIONS.find((o) => o.value === sortFilter)?.title}
                className="appearance-none h-9 w-9 border-0 bg-transparent font-mono text-[15px] leading-none text-oxford/45 hover:text-oxford/75 transition-colors text-center outline-none cursor-pointer focus:outline-none focus-visible:outline-none focus-visible:ring-0"
              >
                {SORT_OPTIONS.map(({ value, label, title }) => (
                  <option key={value} value={value} title={title}>
                    {label}
                  </option>
                ))}
              </select>
            </div>

            <button
              type="button"
              onClick={onToggleAdvancedFilters}
              aria-expanded={showAdvancedFilters}
              aria-label={showAdvancedFilters ? 'Hide filters' : 'More filters'}
              className={`group inline-flex h-9 w-9 shrink-0 items-center justify-center leading-none transition-colors btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 ${
                showAdvancedFilters || hasActiveFilters ? 'text-oxford' : 'text-oxford/[0.34] hover:text-oxford/55'
              }`}
            >
              <span
                aria-hidden
                className={`inline-block font-sans text-[1.05rem] leading-none transition-[transform,color] duration-200 ease-out ${showAdvancedFilters ? 'rotate-90' : ''}`}
              >
                ›
              </span>
            </button>
          </div>
        </div>
      </div>

      <AnimatePresence>
        {showAdvancedFilters && (
          <motion.div
            initial={reduceMotion ? false : { height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={reduceMotion ? { opacity: 0 } : { height: 0, opacity: 0 }}
            transition={{ duration: reduceMotion ? 0 : 0.22, ease: tokens.motion.ease }}
            role="region"
            aria-label="Advanced queue filters"
            className="overflow-hidden"
          >
            <div className="mt-phi-2 border-t border-oxford/[0.06] pt-phi-2">
            <div role="group" aria-label="Deal source" className="mb-phi-3 flex min-w-0 flex-col gap-phi-1">
              <p className={productText.mutedLabel}>Source</p>
              <div className="flex flex-wrap gap-phi-2">
                {SOURCE_FILTER_CHIPS.map(({ key, label }) => (
                  <AdvancedChip
                    key={key}
                    active={sourceFilters.has(key)}
                    label={label}
                    onClick={() => onToggleSource(key)}
                  />
                ))}
              </div>
            </div>

            <div className="grid min-w-0 gap-x-phi-6 gap-y-phi-2 md:grid-cols-3">
              <div role="group" aria-label="Partner ruling and outcome" className="flex min-w-0 flex-col gap-phi-1">
                <p className={productText.mutedLabel}>Outcome</p>
                <div className="flex flex-wrap gap-phi-2">
                  {OUTCOME_FILTER_CHIPS.map(({ key, label }) => (
                    <AdvancedChip
                      key={key}
                      active={outcomeFilters.has(key)}
                      label={label}
                      onClick={() => onToggleOutcome(key)}
                    />
                  ))}
                </div>
              </div>

              <div role="group" aria-label="Reviewer signal strength" className="flex min-w-0 flex-col gap-phi-1">
                <p className={productText.mutedLabel}>Review</p>
                <div className="flex flex-wrap gap-phi-2">
                  {REVIEW_FILTER_CHIPS.map(({ key, label }) => (
                    <AdvancedChip
                      key={key}
                      active={reviewFilters.has(key)}
                      label={label}
                      onClick={() => onToggleReview(key)}
                    />
                  ))}
                </div>
              </div>

              <div role="group" aria-label="Risk flags" className="flex min-w-0 flex-col gap-phi-1">
                <p className={productText.mutedLabel}>Flags</p>
                <div className="flex flex-wrap gap-phi-2">
                  {FLAG_FILTER_CHIPS.map(({ key, label }) => (
                    <AdvancedChip
                      key={key}
                      active={flagFilters.has(key)}
                      label={label}
                      onClick={() => onToggleFlag(key)}
                    />
                  ))}
                </div>
              </div>
            </div>

            {hasActiveFilters && (
              <button
                type="button"
                onClick={onResetFilters}
                className={`${productInteraction.action} mt-phi-2 shrink-0 !min-h-[36px]`}
              >
                Reset
              </button>
            )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
