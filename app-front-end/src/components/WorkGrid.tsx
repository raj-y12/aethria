import { useMemo, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Startup } from '../types/startup';
import { getReviewerQualityBand } from '../design-system/semantics';
import { tokens } from '../design-system/tokens';
import {
  UI_FILTER_TOOLBAR_LABEL,
} from '../design-system/ui-text';
import { usePrefersReducedMotion } from '../hooks';
import DecisionBadge from './DecisionBadge';
import VerdictBandBadge from './VerdictBandBadge';
import EmptyState from './EmptyState';
import { resolveEscalation } from '../api/escalations';

interface RowDecisionState { decision: string | null; notes: string; resolved: boolean; }
const emptyRowState = (): RowDecisionState => ({ decision: null, notes: '', resolved: false });

type SourceFilter = 'ALL' | 'SCOUT' | 'LOOKUP';
type DecisionFilter = 'ALL' | 'YES' | 'NO' | 'MAYBE' | 'ESCALATION' | 'UNDECIDED' | 'AWAITING_REVIEW';
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

function getDecisionBadgeVariant(s: Startup): 'INVEST' | 'PASS' | 'MONITOR' | 'awaiting' | 'undecided' | 'escalation' {
  if (s.partner != null && s.partner.human_review_required === true) return 'escalation';
  const rec = s.partner?.recommendation;
  if (!rec) return s.review ? 'undecided' : 'awaiting';
  if (rec === 'INVEST') return 'INVEST';
  if (rec === 'PASS') return 'PASS';
  return 'MONITOR';
}

const FilterButton = ({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) => (
  <button
    type="button"
    onClick={onClick}
    className={`type-meta min-h-[36px] px-2 transition-[color,border-color,background-color] duration-200 border-b focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 ${active ? 'border-oxford text-oxford' : 'border-transparent text-oxford/45 hover:text-oxford/70'
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

const WorkGrid = ({ startups, onStartupClick, selectedId }: WorkGridProps): JSX.Element => {
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('ALL');
  const [decisionFilter, setDecisionFilter] = useState<DecisionFilter>('ALL');
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>('ALL');
  const [sortFilter, setSortFilter] = useState<SortFilter>('NEWEST');
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [rowDecisions, setRowDecisions] = useState<Record<string, RowDecisionState>>({});
  const reduceMotion = usePrefersReducedMotion();

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
      if (decisionFilter !== 'ALL' && getDecisionFilterValue(s) !== decisionFilter) return false;
      if (reviewFilter === 'UNREVIEWED' && s.review != null) return false;
      if (reviewFilter !== 'ALL' && reviewFilter !== 'UNREVIEWED' && getReviewerVerdict(s) !== reviewFilter) return false;
      return true;
    });
    return filtered;
  }, [startups, sourceFilter, decisionFilter, reviewFilter, sortFilter]);

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
    <div className="w-full font-sans bg-paper selection:bg-oxford selection:text-paper">
      <div className="sticky top-0 z-20 bg-paper border-b border-oxford/[0.06] px-phi-3 py-phi-2">
        <div className="flex flex-col gap-phi-3">
          <div className="flex flex-wrap items-center justify-between gap-x-phi-4 gap-y-phi-2">
            <div className="flex min-w-0 flex-wrap items-center gap-phi-3">
              <span className={UI_FILTER_TOOLBAR_LABEL}>Deals</span>
              <div className="flex items-center gap-0.5">
                <FilterButton active={sourceFilter === 'ALL'} label="Universe" onClick={() => setSourceFilter('ALL')} />
                <FilterButton active={sourceFilter === 'SCOUT'} label="Scout" onClick={() => setSourceFilter('SCOUT')} />
                <FilterButton active={sourceFilter === 'LOOKUP'} label="Lookup" onClick={() => setSourceFilter('LOOKUP')} />
              </div>
            </div>
            <div className="flex items-center gap-phi-3">
              <div className="relative group">
                <select
                  value={sortFilter}
                  onChange={(e) => setSortFilter(e.target.value as SortFilter)}
                  className="appearance-none min-h-[36px] bg-transparent type-meta tracking-wide text-oxford/55 hover:text-oxford transition-colors pr-6 outline-none cursor-pointer"
                >
                  <option value="NEWEST">Chronological ↓</option>
                  <option value="OLDEST">Chronological ↑</option>
                  <option value="CONFIDENCE_HIGH">Scout Signal ↓</option>
                  <option value="CONFIDENCE_LOW">Scout Signal ↑</option>
                  <option value="NAME_AZ">Identity A–Z</option>
                </select>
                <div className="absolute right-0 top-1/2 -translate-y-1/2 pointer-events-none text-oxford/20">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 9l6 6 6-6" /></svg>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
                className="type-meta min-h-[36px] text-oxford/55 hover:text-oxford transition-colors pl-phi-2"
              >
                {showAdvancedFilters ? 'Collapse' : 'Refine'}
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
                className="border-t border-oxford/[0.06]"
              >
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-phi-4 pt-phi-3">
                  <div className="space-y-2">
                    <span className="type-meta text-oxford/45">Decision</span>
                    <div className="flex flex-wrap gap-2">
                      {['ALL', 'YES', 'NO', 'MAYBE', 'ESCALATION'].map((d) => (
                        <button
                          key={d}
                          onClick={() => setDecisionFilter(d as DecisionFilter)}
                          className={`type-meta px-3 min-h-[36px] border border-oxford/10 transition-colors ${decisionFilter === d ? 'bg-oxford text-paper' : 'hover:bg-oxford/5 text-oxford/60'
                            }`}
                        >
                          {d === 'ALL' ? 'Any' : d}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="space-y-2">
                    <span className="type-meta text-oxford/45">Review band</span>
                    <div className="flex flex-wrap gap-2">
                      {['ALL', 'STRONG', 'MEDIUM', 'WEAK', 'UNREVIEWED'].map((r) => (
                        <button
                          key={r}
                          onClick={() => setReviewFilter(r as ReviewFilter)}
                          className={`type-meta px-3 min-h-[36px] border border-oxford/10 transition-colors ${reviewFilter === r ? 'bg-oxford text-paper' : 'hover:bg-oxford/5 text-oxford/60'
                            }`}
                        >
                          {r === 'ALL' ? 'Any' : r}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-end justify-end">
                    <button
                      onClick={() => {
                        setSourceFilter('ALL');
                        setDecisionFilter('ALL');
                        setReviewFilter('ALL');
                        setSortFilter('NEWEST');
                      }}
                      className="type-meta min-h-[36px] text-oxford/55 hover:text-accent transition-colors underline underline-offset-4"
                    >
                      Reset filters
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
        className="flex flex-col relative"
        layout
        initial={reduceMotion ? false : 'hidden'}
        animate="visible"
        variants={reduceMotion ? {} : {
          hidden: {},
          visible: { transition: { staggerChildren: 0.04, delayChildren: 0.05 } },
        }}
      >
        {ordered.map((startup) => {
          const isSelected = selectedId === startup.id;
          const reviewBand = getReviewerVerdict(startup);
          const decisionVariant = getDecisionBadgeVariant(startup);
          const confidence = startup.scout.confidence ?? 0;
          const displayIndex = (stableIndex.get(startup.id) ?? 0).toString().padStart(2, '0');

          return (
            <motion.div
              key={startup.id}
              layout
              variants={reduceMotion ? {} : {
                hidden: { opacity: 0, x: -8 },
                visible: { opacity: 1, x: 0, transition: { duration: 0.4, ease: tokens.motion.ease } },
              }}
              transition={{ layout: { duration: reduceMotion ? 0 : 0.24, ease: tokens.motion.ease } }}
              className={`group relative border-b border-oxford/[0.06] px-phi-3 cursor-pointer transition-[padding,background-color] duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 ${isSelected ? 'bg-registerTint py-phi-5' : 'hover:bg-oxford/[0.02] py-phi-4'
                }`}
              onClick={() => onStartupClick(startup)}
              onKeyDown={(e) => {
                if (e.target !== e.currentTarget) return;
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onStartupClick(startup);
                }
              }}
              role="button"
              tabIndex={0}
              aria-pressed={isSelected}
              aria-label={`Open memo for ${startup.scout.name}`}
            >
              <div className="grid grid-cols-1 sm:grid-cols-[26px_minmax(0,1fr)_auto] gap-x-phi-3 gap-y-phi-3 items-start">
                {/* Index */}
                <span className="type-meta text-oxford/20 group-hover:text-oxford/40 transition-colors tabular-nums pt-px sm:col-start-1">
                  {displayIndex}
                </span>

                {/* Body */}
                <div className="min-w-0 sm:col-start-2">
                  <h2 className="type-body-emphasis text-oxford">
                    {startup.scout.name}
                  </h2>
                  <div className="flex flex-wrap items-center gap-x-1 mt-phi-2">
                    {sortKey(startup) && (
                      <span className="type-meta text-oxford/30 tabular-nums whitespace-nowrap">
                        {new Date(sortKey(startup)).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
                      </span>
                    )}
                    {(startup.scout.sector || '').split('/')[0].trim() && (
                      <>
                        <span className="type-meta text-oxford/20">·</span>
                        <span className="type-meta text-oxford/30">{(startup.scout.sector || 'Unknown').split('/')[0].trim()}</span>
                      </>
                    )}
                    {startup.scout.funding_stage && (
                      <>
                        <span className="type-meta text-oxford/20">·</span>
                        <span className="type-meta text-oxford/30">{startup.scout.funding_stage}</span>
                      </>
                    )}
                    <span className="type-meta text-oxford/20">·</span>
                    <span className="type-meta text-oxford/30 uppercase">{getSourceBadge(startup)}</span>
                    <span className="type-meta text-oxford/20">·</span>
                    <span
                      className="type-meta text-oxford/30 tabular-nums"
                      title="Scout-stage confidence"
                      aria-label={`Scout signal ${Math.round(confidence * 100)} percent`}
                    >
                      {Math.round(confidence * 100)}%
                    </span>
                  </div>
                  <div className={`overflow-hidden transition-[max-height,opacity,margin] duration-200 ease-out ${isSelected ? 'max-h-24 opacity-100 mt-phi-3' : 'max-h-0 opacity-0'
                    }`}>
                    {startup.scout.one_line && (
                      <p className="type-note italic text-oxford/55">
                        {startup.scout.one_line}
                      </p>
                    )}
                  </div>
                </div>

                {/* Right: badges only */}
                <div className="flex items-center gap-phi-2 pt-px sm:col-start-3">
                  {reviewBand && <VerdictBandBadge band={reviewBand} />}
                  <DecisionBadge variant={decisionVariant} />
                </div>
              </div>

              {/* Resolve panel */}
              <AnimatePresence initial={false}>
                {isSelected && (() => {
                  const rs = getRS(startup.id);
                  return (
                    <motion.div
                      key="decision-panel"
                      layout
                      initial={{ opacity: 0, y: -6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.25, ease: 'easeOut' }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="mt-phi-3 pt-phi-3 border-t border-oxford/[0.06] space-y-phi-4">
                        {rs.resolved ? (
                          <div className="flex items-start gap-phi-4">
                            <DecisionBadge variant={
                              rs.decision === 'YES' ? 'INVEST' : rs.decision === 'NO' ? 'PASS' : 'MONITOR'
                            } />
                            {rs.notes && (
                              <span className="type-meta text-oxford/40 leading-relaxed">{rs.notes}</span>
                            )}
                          </div>
                        ) : (
                          <>
                            <div className="bg-oxford/[0.02] px-phi-2 py-phi-2">
                              <div className="flex flex-wrap items-center justify-between gap-phi-3">
                                <div className="flex items-center gap-phi-2">
                                  <span className="type-meta text-oxford/35 uppercase tracking-[0.16em] shrink-0">Decision</span>
                                  <span className="type-meta text-oxford/25">Select outcome</span>
                                </div>
                                {rs.decision && (
                                  <span className="type-meta text-oxford/45 uppercase tracking-[0.12em]">
                                    {rs.decision === 'YES' ? 'Invest selected' : rs.decision === 'NO' ? 'Pass selected' : 'Monitor selected'}
                                  </span>
                                )}
                              </div>
                              <div className="mt-phi-2 grid grid-cols-1 sm:grid-cols-3 gap-phi-1.5">
                                {([
                                  { d: 'YES' as const, label: 'Invest' },
                                  { d: 'NO' as const, label: 'Pass' },
                                  { d: 'MAYBE' as const, label: 'Monitor' },
                                ] as const).map(({ d, label }) => {
                                  const isActive = rs.decision === d;
                                  const activeClass = d === 'YES'
                                    ? 'bg-oxford border-oxford text-paper'
                                    : d === 'NO'
                                      ? 'border-oxford/45 text-oxford/75 bg-paper'
                                      : 'border-oxford/35 text-oxford/75 bg-paper';
                                  return (
                                    <button
                                      key={d}
                                      type="button"
                                      onClick={() => setRS(startup.id, { decision: isActive ? null : d, notes: isActive ? '' : rs.notes })}
                                      aria-pressed={isActive}
                                      className={`type-meta tracking-[0.1em] uppercase border px-phi-2.5 py-phi-1 transition-all duration-150 btn-interaction inline-flex items-center justify-center min-h-[34px] ${isActive ? activeClass : 'border-oxford/15 text-oxford/45 hover:border-oxford/35 hover:text-oxford/75 bg-transparent'}`}
                                    >
                                      {label}
                                    </button>
                                  );
                                })}
                              </div>
                            </div>
                            <AnimatePresence>
                              {rs.decision && (
                                <motion.div
                                  key="notes-row"
                                  initial={{ opacity: 0, y: -4 }}
                                  animate={{ opacity: 1, y: 0 }}
                                  exit={{ opacity: 0, y: -4 }}
                                  transition={{ duration: 0.18, ease: 'easeOut' }}
                                  className="flex flex-wrap items-end gap-phi-4"
                                >
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
                                    className="type-meta text-oxford/65 hover:text-oxford transition-colors disabled:opacity-20 tracking-[0.12em] inline-flex items-center min-h-[36px] whitespace-nowrap"
                                  >
                                    Confirm →
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => setRS(startup.id, emptyRowState())}
                                    aria-label={`Clear escalation resolution for ${startup.scout.name}`}
                                    className="type-meta text-oxford/30 hover:text-oxford/60 transition-colors tracking-[0.12em] inline-flex items-center min-h-[36px]"
                                  >
                                    ×
                                  </button>
                                </motion.div>
                              )}
                            </AnimatePresence>
                          </>
                        )}
                      </div>
                    </motion.div>
                  );
                })()}
              </AnimatePresence>
            </motion.div>
          );
        })}
      </motion.div>
    </div>
  );
};

export default WorkGrid;
