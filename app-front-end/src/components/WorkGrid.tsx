import { useMemo, useState, useCallback, useRef } from 'react';
import { motion, AnimatePresence, type Variants } from 'framer-motion';
import type { Startup } from '../types/startup';
import { getReviewerQualityBand } from '../design-system/semantics';
import { tokens } from '../design-system/tokens';
import { transitionOrReduced } from '../design-system/motion';
import { usePrefersReducedMotion } from '../hooks';
import DecisionBadge from './DecisionBadge';
import VerdictBandBadge from './VerdictBandBadge';
import EmptyState from './EmptyState';
import { resolveEscalation } from '../api/escalations';
import { getDecisionBadgeVariant } from '../lib/decisionBadgeVariant';

interface RowDecisionState { decision: string | null; notes: string; resolved: boolean; }
const emptyRowState = (): RowDecisionState => ({ decision: null, notes: '', resolved: false });

type SourceFilter = 'ALL' | 'SCOUT' | 'LOOKUP';
type DecisionFilter =
  | 'ALL'
  | 'YES'
  | 'NO'
  | 'MAYBE'
  | 'ESCALATION'
  | 'WATCHLIST'
  | 'UNDECIDED'
  | 'AWAITING_REVIEW';
type ReviewFilter = 'ALL' | 'STRONG' | 'MEDIUM' | 'WEAK' | 'UNREVIEWED';
type SortFilter = 'NEWEST' | 'OLDEST' | 'CONFIDENCE_HIGH' | 'CONFIDENCE_LOW' | 'NAME_AZ';

function getReviewerVerdict(s: Startup) {
  return getReviewerQualityBand(s.review);
}

function getSourceBadge(startup: Startup): 'LOOKUP' | 'SCOUT' {
  return (startup.scout.origin_type ?? '').toLowerCase() === 'on_demand_lookup' ? 'LOOKUP' : 'SCOUT';
}

function sortKey(s: Startup): string {
  return s.timestamps?.partnered_at ?? s.timestamps?.reviewed_at ?? s.timestamps?.discovered_at ?? '';
}

function getDecisionFilterValue(s: Startup): Exclude<DecisionFilter, 'ALL'> {
  if (s.partner?.human_review_required) return 'ESCALATION';
  const rec = s.partner?.recommendation;
  if (rec === 'INVEST') return 'YES';
  if (rec === 'PASS') return 'NO';
  if (rec === 'MONITOR') return 'MAYBE';
  if (s.review) return 'UNDECIDED';
  return 'AWAITING_REVIEW';
}

const FilterButton = ({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) => (
  <button
    type="button"
    onClick={onClick}
    className={`type-label-tab min-h-[36px] px-phi-3 transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 ${active ? 'text-oxford font-semibold' : 'text-oxford/30 hover:text-oxford/60'
      }`}
  >
    {label}
  </button>
);

interface WorkGridProps {
  startups: Startup[];
  onStartupClick: (startup: Startup) => void;
  selectedId?: string | null;
  watchlistIds?: Set<string>;
}

const EMPTY_WATCHLIST_IDS = new Set<string>();

const DECISION_FILTER_CHIPS: { key: DecisionFilter; label: string }[] = [
  { key: 'ALL', label: 'ANY' },
  { key: 'YES', label: 'YES' },
  { key: 'NO', label: 'NO' },
  { key: 'MAYBE', label: 'MAYBE' },
  { key: 'ESCALATION', label: 'ESCALATION' },
  { key: 'WATCHLIST', label: 'MONITOR LIST' },
];

const WorkGrid = ({ startups, onStartupClick, selectedId, watchlistIds }: WorkGridProps): JSX.Element => {
  const watchlistSet = watchlistIds ?? EMPTY_WATCHLIST_IDS;
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('ALL');
  const [decisionFilter, setDecisionFilter] = useState<DecisionFilter>('ALL');
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>('ALL');
  const [sortFilter, setSortFilter] = useState<SortFilter>('NEWEST');
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [rowDecisions, setRowDecisions] = useState<Record<string, RowDecisionState>>({});
  const reduceMotion = usePrefersReducedMotion();

  /** Shared timing so teaser collapse and decision panel exit stay in sync (avoids stutter). */
  const rowExpandTransition = useMemo(
    () =>
      transitionOrReduced(reduceMotion, {
        duration: 0.22,
        ease: tokens.motion.ease,
      }),
    [reduceMotion]
  );
  const decisionPanelTransition = rowExpandTransition;
  const listContainerVariants = useMemo((): Variants | undefined =>
    reduceMotion
      ? undefined
      : {
          hidden: {},
          // 40ms stagger — within Emil's 30-80ms guideline. Short enough to feel snappy.
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

  const getRS = (id: string): RowDecisionState => rowDecisions[id] ?? emptyRowState();

  const setRS = useCallback((id: string, patch: Partial<RowDecisionState>) => {
    setRowDecisions(prev => ({ ...prev, [id]: { ...(prev[id] ?? emptyRowState()), ...patch } }));
  }, []);

  const handleConfirm = useCallback(async (startupId: string) => {
    const rs = rowDecisions[startupId] ?? emptyRowState();
    if (!rs.decision || rs.notes.trim().length < 5) return;
    try {
      await resolveEscalation(startupId, rs.decision as 'YES' | 'NO' | 'MAYBE', rs.notes);
      setRS(startupId, { resolved: true });
    } catch { /* silent */ }
  }, [rowDecisions, setRS]);

  const stableIndex = useMemo(() => {
    // Reference numbers are always chronological by discovery (oldest = 01), independent of sort
    const byDiscovery = [...startups].sort((a, b) => sortKey(a).localeCompare(sortKey(b)));
    return new Map(byDiscovery.map((s, i) => [s.id, i + 1]));
  }, [startups]);

  const ordered = useMemo(() => {
    const sorted = [...startups];
    switch (sortFilter) {
      case 'OLDEST':
        sorted.sort((a, b) => sortKey(a).localeCompare(sortKey(b)));
        break;
      case 'CONFIDENCE_HIGH':
        sorted.sort((a, b) => (b.scout.confidence ?? 0) - (a.scout.confidence ?? 0));
        break;
      case 'CONFIDENCE_LOW':
        sorted.sort((a, b) => (a.scout.confidence ?? 0) - (b.scout.confidence ?? 0));
        break;
      case 'NAME_AZ':
        sorted.sort((a, b) => (a.scout.name ?? '').localeCompare(b.scout.name ?? ''));
        break;
      case 'NEWEST':
      default:
        sorted.sort((a, b) => sortKey(b).localeCompare(sortKey(a)));
        break;
    }
    const filtered = sorted.filter((s) => {
      if (sourceFilter === 'LOOKUP' && getSourceBadge(s) !== 'LOOKUP') return false;
      if (sourceFilter === 'SCOUT' && getSourceBadge(s) !== 'SCOUT') return false;
      if (decisionFilter === 'WATCHLIST') {
        if (!watchlistSet.has(s.id)) return false;
      } else if (decisionFilter !== 'ALL' && getDecisionFilterValue(s) !== decisionFilter) {
        return false;
      }
      if (reviewFilter === 'UNREVIEWED' && s.review != null) return false;
      if (reviewFilter !== 'ALL' && reviewFilter !== 'UNREVIEWED' && getReviewerVerdict(s) !== reviewFilter) return false;
      return true;
    });
    return filtered;
  }, [startups, sourceFilter, decisionFilter, reviewFilter, sortFilter, watchlistSet]);

  // Arrow-key navigation between rows — power-user keyboard flow
  const handleRowKeyDown = useCallback(
    (e: React.KeyboardEvent, startup: (typeof ordered)[number], idx: number) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onStartupClick(startup);
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        const next = ordered[idx + 1];
        if (next) rowRefs.current.get(next.id)?.focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const prev = ordered[idx - 1];
        if (prev) rowRefs.current.get(prev.id)?.focus();
      }
    },
    [onStartupClick, ordered]
  );

  if (startups.length === 0) {
    return (
      <div className="w-full h-full min-h-[12rem] flex flex-col items-center justify-center">
        <EmptyState
          label="Pipeline"
          body="Scouts are filling the queue. First companies usually appear within a few minutes."
        />
      </div>
    );
  }

  return (
    <div className="w-full font-sans bg-surface-canvas selection:bg-oxford selection:text-paper">
      <div className="sticky top-0 z-20 bg-surface-canvas px-phi-4 py-phi-3">
        <div className="flex flex-col gap-phi-3 uppercase tracking-[0.06em]">
          <div className="flex flex-wrap items-center justify-between gap-x-phi-4 gap-y-phi-2">
            <div className="flex min-w-0 flex-wrap items-center gap-phi-3">
              <div className="flex items-center gap-0">
                <FilterButton active={sourceFilter === 'ALL'} label="ALL" onClick={() => setSourceFilter('ALL')} />
                <FilterButton active={sourceFilter === 'SCOUT'} label="SCOUT" onClick={() => setSourceFilter('SCOUT')} />
                <FilterButton active={sourceFilter === 'LOOKUP'} label="LOOKUP" onClick={() => setSourceFilter('LOOKUP')} />
              </div>
            </div>
            <div className="flex items-center gap-phi-3">
              <div className="relative group">
                <select
                  value={sortFilter}
                  onChange={(e) => setSortFilter(e.target.value as SortFilter)}
                  aria-label="Sort deals"
                  className="appearance-none min-h-[36px] bg-transparent type-meta text-oxford/30 hover:text-oxford/60 transition-colors pr-6 outline-none cursor-pointer"
                >
                  <option value="NEWEST">CHRONOLOGICAL ↓</option>
                  <option value="OLDEST">CHRONOLOGICAL ↑</option>
                  <option value="CONFIDENCE_HIGH">SCOUT SIGNAL ↓</option>
                  <option value="CONFIDENCE_LOW">SCOUT SIGNAL ↑</option>
                  <option value="NAME_AZ">IDENTITY A–Z</option>
                </select>
                <div className="absolute right-0 top-1/2 -translate-y-1/2 pointer-events-none text-oxford/20">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 9l6 6 6-6" /></svg>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
                className="type-meta min-h-[36px] text-oxford/30 hover:text-oxford/60 transition-colors pl-phi-2"
              >
                {showAdvancedFilters ? 'COLLAPSE' : 'REFINE'}
              </button>
            </div>
          </div>

          <AnimatePresence>
            {showAdvancedFilters && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.2, ease: tokens.motion.ease }}
                className="pt-phi-3 mt-phi-1"
              >
                <div className="flex flex-col gap-phi-4 pt-phi-3">
                  <div className="flex flex-col sm:flex-row sm:items-start gap-phi-2 sm:gap-phi-4">
                    <span className="type-label-tab text-oxford/30 sm:w-[112px] sm:shrink-0 sm:pt-[10px]">DECISION</span>
                    <div className="flex flex-wrap gap-phi-2 flex-1 min-w-0">
                      {DECISION_FILTER_CHIPS.map(({ key: d, label }) => (
                        <button
                          key={d}
                          type="button"
                          onClick={() => setDecisionFilter(d)}
                          className={`type-meta px-phi-3 min-h-[34px] transition-colors ${decisionFilter === d ? 'bg-oxford text-paper' : 'bg-registerTint hover:bg-oxford/[0.06] text-oxford/60'
                            }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex flex-col sm:flex-row sm:items-start gap-phi-2 sm:gap-phi-4">
                    <span className="type-label-tab text-oxford/30 sm:w-[112px] sm:shrink-0 sm:pt-[10px]">REVIEW BAND</span>
                    <div className="flex flex-wrap gap-phi-2 flex-1 min-w-0">
                      {['ALL', 'STRONG', 'MEDIUM', 'WEAK', 'UNREVIEWED'].map((r) => (
                        <button
                          key={r}
                          onClick={() => setReviewFilter(r as ReviewFilter)}
                          className={`type-meta px-phi-3 min-h-[34px] transition-colors ${reviewFilter === r ? 'bg-oxford text-paper' : 'bg-registerTint hover:bg-oxford/[0.06] text-oxford/60'
                            }`}
                        >
                          {r === 'ALL' ? 'ANY' : r}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex justify-end pt-phi-2 border-t border-oxford/[0.06]">
                    <button
                      onClick={() => {
                        setSourceFilter('ALL');
                        setDecisionFilter('ALL');
                        setReviewFilter('ALL');
                        setSortFilter('NEWEST');
                      }}
                      className="type-meta min-h-[36px] text-oxford/30 hover:text-oxford/60 transition-colors"
                    >
                      RESET FILTERS
                    </button>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      <motion.div
        key={`${sourceFilter}-${decisionFilter}-${reviewFilter}-${sortFilter}`}
        className="flex flex-col relative [contain:layout_style]"
        initial={reduceMotion ? false : 'hidden'}
        animate="visible"
        variants={listContainerVariants}
      >
        {ordered.map((startup, idx) => {
          const isSelected = selectedId === startup.id;
          const reviewBand = getReviewerVerdict(startup);
          const decisionVariant = getDecisionBadgeVariant(startup);
          const displayIndex = (stableIndex.get(startup.id) ?? 0).toString().padStart(2, '0');
          const onMonitorList = watchlistSet.has(startup.id);
          const rowAria = `${startup.scout.name} — ${startup.scout.sector ?? 'Unknown sector'}.${
            onMonitorList ? ' On system monitor list.' : ''
          } Press Enter to open memo.`;

          return (
            <motion.div
              key={startup.id}
              ref={(el) => {
                if (el) rowRefs.current.set(startup.id, el);
                else rowRefs.current.delete(startup.id);
              }}
              variants={rowVariants}
              className={`group relative px-phi-4 py-phi-6 cursor-pointer transition-[background-color] duration-[180ms] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 focus-visible:ring-inset hover:bg-registerTint ${isSelected ? 'bg-registerTint' : ''
                }`}
              style={{ transitionTimingFunction: 'var(--motion-ease)' }}
              onClick={() => onStartupClick(startup)}
              onKeyDown={(e) => handleRowKeyDown(e, startup, idx)}
              role="button"
              tabIndex={0}
              aria-pressed={isSelected}
              aria-label={rowAria}
            >
              <div className="grid grid-cols-1 sm:grid-cols-[26px_minmax(0,1fr)_auto] gap-x-phi-4 gap-y-phi-3 items-start">
                {/* Index */}
                <span className="type-meta text-oxford/25 group-hover:text-oxford/45 transition-colors tabular-nums pt-px sm:col-start-1">
                  {displayIndex}
                </span>

                {/* Body */}
                <div className="min-w-0 sm:col-start-2">
                  <h2 className="type-body-emphasis text-oxford">
                    {startup.scout.name}
                  </h2>
                  <div className="flex flex-wrap items-center gap-x-phi-2 mt-phi-2">
                    {sortKey(startup) && (
                      <span className="type-meta text-oxford/35 tabular-nums whitespace-nowrap">
                        {new Date(sortKey(startup)).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
                      </span>
                    )}
                    {(startup.scout.sector || '').split('/')[0].trim() && (
                      <>
                        <span className="type-meta text-oxford/25">·</span>
                        <span className="type-meta text-oxford/50">{(startup.scout.sector || 'Unknown').split('/')[0].trim()}</span>
                      </>
                    )}
                    {startup.scout.funding_stage && (
                      <>
                        <span className="type-meta text-oxford/25">·</span>
                        <span className="type-meta text-oxford/35">{startup.scout.funding_stage}</span>
                      </>
                    )}
                    {getSourceBadge(startup) === 'LOOKUP' && (
                      <>
                        <span className="type-meta text-oxford/25">·</span>
                        <span className="type-meta tracking-[0.08em] text-lookup">Lookup</span>
                      </>
                    )}
                  </div>
                </div>

                {/* Right: monitor chip, review band, partner verdict badge */}
                <div className="flex flex-wrap items-center justify-end gap-phi-2 pt-px sm:col-start-3">
                  {onMonitorList && (
                    <span
                      className="type-label-tab text-oxford/45 bg-registerTint px-phi-2 py-0.5 shrink-0"
                      title="Tracked on portfolio monitor list (partner monitor outcome)"
                    >
                      Monitor
                    </span>
                  )}
                  {reviewBand && <VerdictBandBadge band={reviewBand} />}
                  <DecisionBadge variant={decisionVariant} />
                </div>
              </div>

              {/* Resolve panel: animate layout height, not only opacity, to avoid instant collapse. */}
              <div
                className={`grid min-h-0 transition-[grid-template-rows] ease-out ${isSelected ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'}`}
                style={{
                  transitionDuration: reduceMotion ? '0ms' : '220ms',
                  transitionTimingFunction: tokens.motion.easeCss,
                }}
                aria-hidden={!isSelected}
              >
                <div className={`min-h-0 overflow-hidden ${isSelected ? '' : 'pointer-events-none'}`}>
                  <AnimatePresence initial={false}>
                    {isSelected && (() => {
                      const rs = getRS(startup.id);
                      return (
                        <motion.div
                          key="decision-panel"
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          transition={decisionPanelTransition}
                          onClick={(e) => e.stopPropagation()}
                        >
                          <div className="mt-phi-4 pt-phi-4 space-y-phi-4">
                            {rs.resolved ? (
                              <motion.div
                                className="flex items-start gap-phi-4"
                                initial={reduceMotion ? false : { opacity: 0, x: -6 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={transitionOrReduced(reduceMotion, { duration: 0.3, ease: tokens.motion.ease })}
                              >
                                <DecisionBadge variant={
                                  rs.decision === 'YES' ? 'INVEST' : rs.decision === 'NO' ? 'PASS' : 'MONITOR'
                                } />
                                {rs.notes && (
                                  <span className="type-meta text-oxford/40 leading-relaxed">{rs.notes}</span>
                                )}
                              </motion.div>
                            ) : (
                              <div className="space-y-phi-3">
                                <div className="flex flex-wrap items-center gap-x-phi-4 gap-y-phi-2">
                                  <span className="type-meta text-oxford/45 tracking-[0.08em] shrink-0">Decision</span>
                                  {([
                                    { d: 'YES' as const, label: 'Invest' },
                                    { d: 'NO' as const, label: 'Pass' },
                                    { d: 'MAYBE' as const, label: 'Monitor' },
                                  ] as const).map(({ d, label }) => {
                                    const isActive = rs.decision === d;
                                    return (
                                      <button
                                        key={d}
                                        type="button"
                                        onClick={() => setRS(startup.id, { decision: isActive ? null : d, notes: isActive ? '' : rs.notes })}
                                        aria-pressed={isActive}
                                        className={`type-meta tracking-[0.08em] min-h-[34px] border-b transition-[color,border-color] duration-150 btn-interaction ${isActive ? 'border-oxford text-oxford font-semibold' : 'border-transparent text-oxford/38 hover:border-oxford/20 hover:text-oxford/70'}`}
                                      >
                                        {label}
                                      </button>
                                    );
                                  })}
                                </div>
                                {rs.decision && (
                                  <div className="flex flex-wrap items-end gap-x-phi-4 gap-y-phi-2">
                                    <textarea
                                      value={rs.notes}
                                      onChange={(e) => setRS(startup.id, { notes: e.target.value })}
                                      placeholder="Rationale..."
                                      aria-label={`Decision rationale for ${startup.scout.name}`}
                                      autoFocus
                                      rows={1}
                                      className="w-full sm:flex-1 bg-transparent border-0 border-b border-oxford/10 py-phi-1 type-meta text-oxford/80 placeholder:text-oxford/20 outline-none focus:border-oxford/30 transition-colors resize-none tracking-[0.04em]"
                                    />
                                    <button
                                      type="button"
                                      onClick={() => handleConfirm(startup.id)}
                                      disabled={rs.notes.trim().length < 5}
                                      className="type-meta text-oxford/65 hover:text-oxford transition-colors disabled:opacity-20 tracking-[0.12em] inline-flex items-center min-h-[34px] whitespace-nowrap"
                                    >
                                      Confirm →
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => setRS(startup.id, emptyRowState())}
                                      className="type-meta text-oxford/30 hover:text-oxford/60 transition-colors tracking-[0.12em] inline-flex items-center min-h-[34px]"
                                    >
                                      Clear
                                    </button>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        </motion.div>
                      );
                    })()}
                  </AnimatePresence>
                </div>
              </div>
            </motion.div>
          );
        })}
      </motion.div>
    </div>
  );
};

export default WorkGrid;
