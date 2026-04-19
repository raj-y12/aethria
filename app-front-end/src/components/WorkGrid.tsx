import { useMemo, useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Startup } from '../types/startup';
import { getReviewerQualityBand } from '../design-system/semantics';
import { tokens } from '../design-system/tokens';
import { transitionOrReduced } from '../design-system/motion';
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

const ORIENT_DISMISSED_KEY = 'aethria_dashboard_orient_dismissed';
const COACH_MARK_DURATION_MS = 4000;

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
    className={`type-label-tab px-3 py-1.5 transition-all duration-300 border-b ${
      active ? 'border-oxford text-oxford bg-oxford/5' : 'border-transparent text-oxford/30 hover:text-oxford/60'
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

  const ordered = useMemo(() => {
    const filtered = startups.filter((s) => {
      if (sourceFilter === 'LOOKUP' && getSourceBadge(s) !== 'LOOKUP') return false;
      if (sourceFilter === 'SCOUT' && getSourceBadge(s) !== 'SCOUT') return false;
      if (decisionFilter !== 'ALL' && getDecisionFilterValue(s) !== decisionFilter) return false;
      if (reviewFilter === 'UNREVIEWED' && s.review != null) return false;
      if (reviewFilter !== 'ALL' && reviewFilter !== 'UNREVIEWED' && getReviewerVerdict(s) !== reviewFilter) return false;
      return true;
    });
    const list = [...filtered];
    switch (sortFilter) {
      case 'OLDEST':
        list.sort((a, b) => sortKey(a).localeCompare(sortKey(b)));
        break;
      case 'CONFIDENCE_HIGH':
        list.sort((a, b) => (b.scout.confidence ?? 0) - (a.scout.confidence ?? 0));
        break;
      case 'CONFIDENCE_LOW':
        list.sort((a, b) => (a.scout.confidence ?? 0) - (b.scout.confidence ?? 0));
        break;
      case 'NAME_AZ':
        list.sort((a, b) => (a.scout.name ?? '').localeCompare(b.scout.name ?? ''));
        break;
      case 'NEWEST':
      default:
        list.sort((a, b) => sortKey(b).localeCompare(sortKey(a)));
        break;
    }
    return list;
  }, [startups, sourceFilter, decisionFilter, reviewFilter, sortFilter]);

  const [showCoachMark, setShowCoachMark] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined' || startups.length === 0) return;
    try {
      if (!window.localStorage.getItem(ORIENT_DISMISSED_KEY)) setShowCoachMark(true);
    } catch { /* ignore */ }
  }, [startups.length]);

  useEffect(() => {
    if (!showCoachMark) return;
    const t = window.setTimeout(() => {
      try {
        window.localStorage.setItem(ORIENT_DISMISSED_KEY, '1');
      } catch { /* ignore */ }
      setShowCoachMark(false);
    }, COACH_MARK_DURATION_MS);
    return () => clearTimeout(t);
  }, [showCoachMark]);

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
      {/* Editorial Toolbar — Museum Grade */}
      <div className="sticky top-0 z-20 bg-paper/90 backdrop-blur-md border-b border-oxford/[0.06] px-phi-4 py-phi-4">
        <div className="flex flex-col gap-phi-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-phi-4">
              <span className={UI_FILTER_TOOLBAR_LABEL}>Archive</span>
              <div className="flex items-center gap-1">
                <FilterButton active={sourceFilter === 'ALL'} label="Universe" onClick={() => setSourceFilter('ALL')} />
                <FilterButton active={sourceFilter === 'SCOUT'} label="Scout" onClick={() => setSourceFilter('SCOUT')} />
                <FilterButton active={sourceFilter === 'LOOKUP'} label="Lookup" onClick={() => setSourceFilter('LOOKUP')} />
              </div>
            </div>
            <div className="flex items-center gap-phi-4">
              <div className="relative group">
                <select
                  value={sortFilter}
                  onChange={(e) => setSortFilter(e.target.value as SortFilter)}
                  className="appearance-none bg-transparent type-meta uppercase tracking-widest text-oxford/40 hover:text-oxford transition-colors pr-6 outline-none cursor-pointer"
                >
                  <option value="NEWEST">Chronological ↓</option>
                  <option value="OLDEST">Chronological ↑</option>
                  <option value="CONFIDENCE_HIGH">Intelligence ↓</option>
                  <option value="CONFIDENCE_LOW">Intelligence ↑</option>
                  <option value="NAME_AZ">Identity A–Z</option>
                </select>
                <div className="absolute right-0 top-1/2 -translate-y-1/2 pointer-events-none text-oxford/20">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 9l6 6 6-6"/></svg>
                </div>
              </div>
              <button
                onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
                className="type-label-tab text-oxford/40 hover:text-oxford transition-colors border-l border-oxford/10 pl-phi-4"
              >
                {showAdvancedFilters ? 'Collapse' : 'Refine'}
              </button>
            </div>
          </div>

          <AnimatePresence>
            {showAdvancedFilters && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden grid grid-cols-1 sm:grid-cols-3 gap-phi-5 pt-phi-4 border-t border-oxford/[0.06]"
              >
                <div className="space-y-2">
                  <span className="type-meta text-oxford/25 uppercase tracking-widest">Economic Decision</span>
                  <div className="flex flex-wrap gap-2">
                    {['ALL', 'YES', 'NO', 'MAYBE', 'ESCALATION'].map((d) => (
                      <button
                        key={d}
                        onClick={() => setDecisionFilter(d as DecisionFilter)}
                        className={`type-meta px-2 py-1 border border-oxford/10 transition-colors ${
                          decisionFilter === d ? 'bg-oxford text-paper' : 'hover:bg-oxford/5 text-oxford/60'
                        }`}
                      >
                        {d === 'ALL' ? 'Any' : d}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="space-y-2">
                  <span className="type-meta text-oxford/25 uppercase tracking-widest">Intelligence Band</span>
                  <div className="flex flex-wrap gap-2">
                    {['ALL', 'STRONG', 'MEDIUM', 'WEAK', 'UNREVIEWED'].map((r) => (
                      <button
                        key={r}
                        onClick={() => setReviewFilter(r as ReviewFilter)}
                        className={`type-meta px-2 py-1 border border-oxford/10 transition-colors ${
                          reviewFilter === r ? 'bg-oxford text-paper' : 'hover:bg-oxford/5 text-oxford/60'
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
                    className="type-label-tab text-oxford/40 hover:text-accent transition-colors underline underline-offset-4"
                  >
                    Reset All Filters
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* The Intelligence River */}
      <motion.div
        key={`${sourceFilter}-${decisionFilter}-${reviewFilter}-${sortFilter}`}
        className="flex flex-col relative"
        initial={reduceMotion ? false : 'hidden'}
        animate="visible"
        variants={reduceMotion ? {} : {
          hidden: {},
          visible: { transition: { staggerChildren: 0.1, delayChildren: 0.15 } },
        }}
      >
        {ordered.map((startup, index) => {
          const isSelected = selectedId === startup.id;
          const reviewBand = getReviewerVerdict(startup);
          const decisionVariant = getDecisionBadgeVariant(startup);
          const confidence = startup.scout.confidence ?? 0;
          const displayIndex = (index + 1).toString().padStart(2, '0');

          return (
            <motion.div
              key={startup.id}
              variants={reduceMotion ? {} : {
                hidden: { opacity: 0, x: -12 },
                visible: { opacity: 1, x: 0, transition: { duration: 0.55, ease: tokens.motion.ease } },
              }}
              className={`group relative border-b border-oxford/[0.06] py-phi-5 px-phi-4 cursor-pointer transition-all duration-700 ease-smooth ${
                isSelected ? 'bg-registerTint' : 'hover:bg-oxford/[0.02]'
              }`}
              onClick={() => onStartupClick(startup)}
            >
              {/* Selected Spine */}
              <AnimatePresence>
                {isSelected && (
                  <motion.div
                    layoutId="selected-spine"
                    className="absolute left-0 top-0 w-1.5 h-full bg-oxford/80"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                  />
                )}
              </AnimatePresence>

              <div className="grid grid-cols-1 gap-phi-5 items-start lg:grid-cols-[76px_minmax(0,1fr)_max-content] 2xl:grid-cols-[100px_minmax(0,1fr)_max-content]">
                {/* 01: Metadata Index */}

                <div className="flex flex-col gap-phi-3 min-w-0">
                  <span className="type-label-section text-oxford/20 group-hover:text-oxford/50 transition-colors duration-500 tabular-nums">
                    Ref_{displayIndex}
                  </span>
                  <div className="relative w-0.5 h-16 bg-oxford/5 overflow-hidden">
                    <motion.div
                      initial={{ height: 0 }}
                      animate={{ height: `${confidence * 100}%` }}
                      transition={{ duration: 1.2, delay: 0.2, ease: "easeOut" }}
                      className="absolute bottom-0 left-0 w-full bg-oxford/30"
                    />
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <span className="type-meta text-oxford/30 uppercase tracking-tighter">Confidence</span>
                    <span className="type-meta text-oxford/50 tabular-nums">
                      {Math.round(confidence * 100)}%
                    </span>
                  </div>
                </div>

                {/* 02: Core Essence */}
                <div className="flex min-w-0 flex-col gap-phi-4">
                  <div className="flex flex-col sm:flex-row sm:items-baseline gap-phi-4">
                    <h2 className="font-sans font-semibold text-xl sm:text-2xl leading-tight text-oxford tracking-tight">
                      {startup.scout.name}
                    </h2>
                  </div>

                  <div className="flex flex-wrap items-center gap-x-phi-4 gap-y-phi-2">
                    {(startup.scout.sector || 'Unassigned').split('/').map((s) => s.trim()).filter(Boolean).map((s) => (
                      <span key={s} className="type-label-tab text-oxford/40 border border-oxford/10 px-2 py-0.5 group-hover:border-oxford/30 transition-colors">
                        {s}
                      </span>
                    ))}
                    <span className="type-meta text-oxford/40 uppercase tracking-widest">{startup.scout.funding_stage || 'Unknown Stage'}</span>
                    <span className="w-1.5 h-1.5 border border-oxford/20 rotate-45" />
                    <span className="type-meta text-oxford/40 uppercase tabular-nums">
                      {getSourceBadge(startup)}
                    </span>
                  </div>

                  {/* One Line Reveal */}
                  <div className={`overflow-hidden transition-all duration-200 ease-out ${
                    isSelected ? 'max-h-32 opacity-100 mt-phi-2' : 'max-h-0 opacity-0 group-hover:max-h-32 group-hover:opacity-100 group-hover:mt-phi-2'
                  }`}>
                    <p className="type-body text-oxford/60 max-w-2xl leading-relaxed italic border-l-2 border-oxford/[0.06] pl-phi-4">
                      {startup.scout.one_line || 'No intelligence summary provided.'}
                    </p>
                  </div>
                </div>

                {/* 03: Decision & Logistics */}
                <div className="flex min-w-0 flex-col items-start gap-phi-5 lg:items-end">
                  <div className="flex flex-col items-start lg:items-end gap-phi-2">
                    <span className="type-meta text-oxford/30 uppercase tracking-widest">Verdict</span>
                    <div className="flex items-center gap-2">
                      {reviewBand && <VerdictBandBadge band={reviewBand} />}
                      <DecisionBadge variant={decisionVariant} />
                    </div>
                  </div>

                  <div className="flex w-full flex-col items-start gap-phi-1 border-t border-oxford/5 pt-phi-4 lg:w-auto lg:items-end">
                    <span className="type-meta text-oxford/30 uppercase">Archived</span>
                    <span className="type-meta text-oxford/50 tabular-nums">
                      {new Date(sortKey(startup)).toLocaleDateString('en-GB', {
                        day: '2-digit',
                        month: 'short',
                        year: 'numeric'
                      })}
                    </span>
                  </div>

                  <motion.span
                    initial={{ opacity: 0 }}
                    animate={isSelected ? { opacity: 1 } : { opacity: 0 }}
                    className="type-meta text-oxford/40 hidden lg:block uppercase tracking-widest mt-auto group-hover:opacity-100 transition-opacity"
                  >
                    Expose Memo →
                  </motion.span>
                </div>
              </div>

              {/* Inline decision panel — visible only when selected */}
              <AnimatePresence>
                {isSelected && (() => {
                  const rs = getRS(startup.id);
                  return (
                    <motion.div
                      key="decision-panel"
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.25, ease: 'easeOut' }}
                      className="overflow-hidden"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="mt-phi-4 pt-phi-4 border-t border-oxford/[0.06]">
                        {rs.resolved ? (
                          <span className="type-meta text-oxford/40 uppercase tracking-widest">Decision recorded</span>
                        ) : !rs.decision ? (
                          <div className="flex items-center gap-phi-6">
                            <span className="type-meta text-oxford/25 uppercase tracking-widest">Resolve:</span>
                            {[
                              { d: 'YES' as const, label: 'Invest' },
                              { d: 'NO' as const, label: 'Pass' },
                              { d: 'MAYBE' as const, label: 'Monitor' },
                            ].map(({ d, label }) => (
                              <button
                                key={d}
                                type="button"
                                onClick={() => setRS(startup.id, { decision: d })}
                                className="type-meta text-oxford/40 hover:text-oxford transition-colors uppercase tracking-[0.18em] underline underline-offset-8 decoration-oxford/10 hover:decoration-oxford/40 btn-interaction"
                              >
                                {label}
                              </button>
                            ))}
                          </div>
                        ) : (
                          <div className="space-y-phi-4">
                            <textarea
                              value={rs.notes}
                              onChange={(e) => setRS(startup.id, { notes: e.target.value })}
                              placeholder="Add a note explaining your decision..."
                              autoFocus
                              rows={2}
                              className="w-full bg-transparent border-0 border-b border-oxford/10 py-2 type-body text-oxford placeholder:text-oxford/20 outline-none focus:border-oxford/30 transition-colors resize-none"
                            />
                            <div className="flex gap-phi-4">
                              <button
                                type="button"
                                onClick={() => handleConfirm(startup.id)}
                                disabled={rs.notes.trim().length < 5}
                                className="type-meta text-oxford hover:text-escalation transition-colors disabled:opacity-20 uppercase tracking-[0.14em]"
                              >
                                Confirm — {rs.decision}
                              </button>
                              <button
                                type="button"
                                onClick={() => setRS(startup.id, emptyRowState())}
                                className="type-meta text-oxford/20 hover:text-oxford transition-colors uppercase tracking-[0.14em]"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
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
