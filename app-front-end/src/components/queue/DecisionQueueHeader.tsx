import { AnimatePresence, motion } from 'framer-motion';
import { tokens } from '../../design-system/tokens';
import { productInteraction, productText } from '../../design-system/productSystem';
import type { FundConfiguration } from '../../lib/fundConfiguration';

export type QueueView = 'ALL' | 'PRIORITY' | 'NEW' | 'STALE' | 'ESCALATED';

export type SourceFilter = 'ALL' | 'SCOUT' | 'LOOKUP';

export type DecisionFilter =
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

export type ReviewFilter = 'ALL' | 'STRONG' | 'MEDIUM' | 'WEAK' | 'UNREVIEWED';

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
  { key: 'ALL', label: 'ALL' },
  { key: 'SCOUT', label: 'SCOUT' },
  { key: 'LOOKUP', label: 'LOOKUP' },
];

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
      className={`type-meta min-h-[36px] whitespace-nowrap px-phi-3 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 ${
        active ? 'bg-oxford text-paper' : 'bg-oxford/[0.035] hover:bg-oxford/[0.065] text-oxford/58'
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
      className={`type-meta min-h-[36px] px-phi-3 transition-colors btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 ${
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
                : 'text-oxford/28'
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
  sourceFilter: SourceFilter;
  onSourceFilterChange: (filter: SourceFilter) => void;
  decisionFilter: DecisionFilter;
  onDecisionFilterChange: (filter: DecisionFilter) => void;
  reviewFilter: ReviewFilter;
  onReviewFilterChange: (filter: ReviewFilter) => void;
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
  sourceFilter,
  onSourceFilterChange,
  decisionFilter,
  onDecisionFilterChange,
  reviewFilter,
  onReviewFilterChange,
  showAdvancedFilters,
  onToggleAdvancedFilters,
  hasActiveFilters,
  onResetFilters,
  reduceMotion,
}: DecisionQueueHeaderProps) {
  return (
    <header className="sticky top-0 z-20 bg-paper px-phi-3 py-phi-2 uppercase tracking-[0.06em]">
      <div className="flex min-w-0 flex-col gap-phi-2">
        <div className="min-w-0 flex flex-col gap-phi-1">
          <p className={productText.mutedLabel}>Decision queue</p>
          <p className="type-meta normal-case tracking-normal text-oxford/32">
            {config.thresholds.staleAfterHours}h stale · {config.risk.sensitivity} risk
          </p>
        </div>

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
                    : key === 'NEW'
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
              className={`inline-flex h-9 w-9 shrink-0 items-center justify-center font-mono text-[17px] leading-none transition-colors btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 ${
                showAdvancedFilters || hasActiveFilters ? 'text-oxford' : 'text-oxford/40 hover:text-oxford/70'
              }`}
            >
              <span aria-hidden>{showAdvancedFilters ? '−' : '+'}</span>
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
            <div role="group" aria-label="Deal source" className="mb-phi-3 flex min-w-0 flex-col gap-phi-1">
              <p className={productText.mutedLabel}>Source</p>
              <div className="flex flex-wrap gap-phi-2">
                {SOURCE_FILTER_CHIPS.map(({ key, label }) => (
                  <AdvancedChip
                    key={key}
                    active={sourceFilter === key}
                    label={label}
                    onClick={() => onSourceFilterChange(key)}
                  />
                ))}
              </div>
            </div>

            <div className="grid min-w-0 gap-x-phi-6 gap-y-phi-2 md:grid-cols-3">
              <div role="group" aria-label="Attention and queue state" className="flex min-w-0 flex-col gap-phi-1">
                <p className={productText.mutedLabel}>Attention</p>
                <div className="flex flex-wrap gap-phi-2">
                  {ATTENTION_FILTER_CHIPS.filter((item) => item.key !== 'ALL').map(({ key, label }) => (
                    <AdvancedChip
                      key={key}
                      active={decisionFilter === key}
                      label={label}
                      onClick={() => onDecisionFilterChange(decisionFilter === key ? 'ALL' : key)}
                    />
                  ))}
                </div>
              </div>

              <div role="group" aria-label="Partner ruling and outcome" className="flex min-w-0 flex-col gap-phi-1">
                <p className={productText.mutedLabel}>Outcome</p>
                <div className="flex flex-wrap gap-phi-2">
                  {RULING_FILTER_CHIPS.map(({ key, label }) => (
                    <AdvancedChip
                      key={key}
                      active={decisionFilter === key}
                      label={label}
                      onClick={() => onDecisionFilterChange(decisionFilter === key ? 'ALL' : key)}
                    />
                  ))}
                </div>
              </div>

              <div role="group" aria-label="Reviewer signal strength" className="flex min-w-0 flex-col gap-phi-1">
                <p className={productText.mutedLabel}>Review</p>
                <div className="flex flex-wrap gap-phi-2">
                  {(['STRONG', 'MEDIUM', 'WEAK', 'UNREVIEWED'] as const).map((r) => (
                    <AdvancedChip
                      key={r}
                      active={reviewFilter === r}
                      label={r}
                      onClick={() => onReviewFilterChange(reviewFilter === r ? 'ALL' : r)}
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
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
