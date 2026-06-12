import { AnimatePresence, motion } from 'framer-motion';
import type { CSSProperties } from 'react';
import { tokens } from '../../design-system/tokens';
import { productInteraction, productText } from '../../design-system/productSystem';
import type { FundConfiguration } from '../../lib/fundConfiguration';

export type QueueView = 'ALL' | 'PRIORITY' | 'NEW' | 'STALE' | 'ESCALATED';

// Multi-select filter groups. An empty set means "no constraint" (show all).
// Within a group the selected chips are OR'd; across groups they are AND'd.
export type SourceFilter = 'SCOUT' | 'LOOKUP';

export type OutcomeFilter = 'YES' | 'NO' | 'MAYBE' | 'DECIDED';

export type FlagFilter = 'ADVERSE';

export type ReviewFilter = 'STRONG' | 'MEDIUM' | 'WEAK' | 'UNREVIEWED';

export type SortFilter = 'QUEUE_PRIORITY' | 'NEWEST' | 'OLDEST' | 'UNRESOLVED_OLDEST';

const SORT_OPTIONS: { value: SortFilter; label: string }[] = [
  { value: 'QUEUE_PRIORITY', label: 'Queue order' },
  { value: 'NEWEST', label: 'Newest first' },
  { value: 'OLDEST', label: 'Oldest first' },
  { value: 'UNRESOLVED_OLDEST', label: 'Longest unresolved' },
];

const SORT_CHEVRON =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='8' viewBox='0 0 8 8'%3E%3Cpath fill='%23001433' fill-opacity='0.4' d='M0 2.5h8L4 6.5z'/%3E%3C/svg%3E\")";

const sortSelectStyle: CSSProperties = { backgroundImage: SORT_CHEVRON };

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
      className={`type-meta min-h-[36px] whitespace-nowrap px-phi-4 transition-colors btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 ${
        active ? 'bg-oxford text-paper' : 'bg-oxford/[0.035] hover:bg-oxford/[0.065] text-oxford/[0.58]'
      }`}
    >
      {label}
    </button>
  );
}

export interface DecisionQueueHeaderProps {
  config: FundConfiguration;
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
  activeFilterCount: number;
  onResetFilters: () => void;
  reduceMotion: boolean;
}

/**
 * The docket's single control line — one quiet mono register beneath the room
 * header. Queue views live in the room header readouts (FlowPage); this line
 * carries only ordering and refinement. No second header, no tab strip.
 */
export default function DecisionQueueHeader({
  config,
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
  activeFilterCount,
  onResetFilters,
  reduceMotion,
}: DecisionQueueHeaderProps) {
  return (
    <div
      className="sticky top-0 z-10 bg-surface-canvas pb-phi-2"
      title={`${config.thresholds.staleAfterHours}h stale · ${config.risk.sensitivity} risk`}
    >
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-x-phi-4 gap-y-phi-1 border-b border-oxford/[0.06] pb-phi-2">
        <span className="type-meta uppercase tracking-[0.12em] text-oxford/[0.32]">Docket</span>

        <div className="flex items-center gap-x-phi-4">
          <label className="flex items-center gap-phi-2">
            <span className="type-meta uppercase tracking-[0.12em] text-oxford/[0.32]">Sort</span>
            <select
              value={sortFilter}
              onChange={(e) => onSortFilterChange(e.target.value as SortFilter)}
              aria-label="Sort deals"
              style={sortSelectStyle}
              className="type-meta h-9 cursor-pointer appearance-none border-0 bg-transparent bg-no-repeat bg-[length:8px] bg-[center_right_2px] pr-5 uppercase tracking-[0.12em] text-oxford/55 outline-none transition-colors hover:text-oxford/80 focus-visible:outline-none"
            >
              {SORT_OPTIONS.map(({ value, label }) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            onClick={onToggleAdvancedFilters}
            aria-expanded={showAdvancedFilters}
            className={`type-meta inline-flex h-9 shrink-0 items-center gap-phi-1 uppercase tracking-[0.12em] transition-colors btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 ${
              showAdvancedFilters || hasActiveFilters
                ? 'text-oxford'
                : 'text-oxford/[0.34] hover:text-oxford/55'
            }`}
          >
            Filters
            {activeFilterCount > 0 ? (
              <span className="tabular-nums text-oxford/55" aria-label={`${activeFilterCount} active`}>
                · {activeFilterCount}
              </span>
            ) : null}
          </button>
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
            <div className="mt-phi-2 pt-phi-2">
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
    </div>
  );
}
