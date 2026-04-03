/**
 * ─── Data audit (Startup on the wire) ─────────────────────────────────────────
 *
 * Source: GET /api/startups → backend `api._backend_to_frontend`. Shapes `scout`,
 * optional `review`, optional `partner`, `timestamps`, `id`. Other Startup fields
 * on the TS type (e.g. human_resolution) may be absent from this payload unless
 * the API mapper is extended.
 *
 * Reviewer verdict (AI quality band):
 *   • Preferred: `review.consensus_verdict` — 'STRONG' | 'MEDIUM' | 'WEAK' | undefined.
 *     Not currently copied in `_backend_to_frontend` (stored in DB as review_info).
 *   • Always mapped today: `review.verdict` — string, typically STRONG|MEDIUM|WEAK;
 *     may be missing if `review` is null (unreviewed).
 *   • Multi-reviewer: `review.reviews[].verdict` — same enum per SingleReview;
 *     not forwarded by API today, but typed for forward compatibility.
 *   • `review.reviewer_disagreement` / `score_variance`: not in `_backend_to_frontend` today.
 *   • If `review` is null/undefined: no verdict (pipeline not through reviewer).
 *
 * Partner decision (recommended / recorded action):
 *   • `partner` null: partner has not run → no `decision`.
 *   • `partner.decision`: 'YES' | 'NO' | 'MAYBE' | 'PASS' | 'WATCH' (PASS/WATCH
 *     are legacy; frontend maps PASS→Pass, WATCH with decision→Hold via badge).
 *   • `partner.human_review_required`: boolean — escalation / needs human eyes;
 *     orthogonal to verdict quality.
 *   • `human_resolution` (when present on client): human override after escalation;
 *     not exposed in current API mapping but used elsewhere for escalation state.
 *
 * ─── Design (this file) ───────────────────────────────────────────────────────
 *
 * DecisionBadge encodes *workflow* (awaiting review, awaiting decision, escalation,
 * Advance/Pass/Hold). That mixes partner outcome with queue state. Users still need
 * the reviewer quality band (STRONG/MEDIUM/WEAK) beside the partner *decision* text.
 *
 * Each row’s right column: source + reviewer pill (VerdictBand) + economic DecisionBadge
 * on the first line; workflow queue badges (awaiting review/decision, human review)
 * on a second line below.
 */

import { useMemo, useState, useEffect, useCallback, type ChangeEvent } from 'react';
import { motion } from 'framer-motion';
import type { Startup } from '../types/startup';
import { getReviewerQualityBand, type ReviewerQualityBand } from '../design-system/semantics';
import { tokens } from '../design-system/tokens';
import { transitionOrReduced } from '../design-system/motion';
import {
  UI_FILTER_SEGMENT_INACTIVE,
  UI_FILTER_TOOLBAR_LABEL,
} from '../design-system/ui-text';
import { usePrefersReducedMotion } from '../hooks';
import DecisionBadge from './DecisionBadge';
import VerdictBandBadge from './VerdictBandBadge';
import EmptyState from './EmptyState';

const ORIENT_DISMISSED_KEY = 'aethria_dashboard_orient_dismissed';
const COACH_MARK_DURATION_MS = 4000;

type SourceFilter = 'ALL' | 'SCOUT' | 'LOOKUP';
type DecisionFilter = 'ALL' | 'YES' | 'NO' | 'MAYBE' | 'ESCALATION' | 'UNDECIDED' | 'AWAITING_REVIEW';
type ReviewFilter = 'ALL' | 'STRONG' | 'MEDIUM' | 'WEAK' | 'UNREVIEWED';
type SortFilter = 'NEWEST' | 'OLDEST' | 'CONFIDENCE_HIGH' | 'CONFIDENCE_LOW' | 'NAME_AZ';

type ReviewerVerdictBand = ReviewerQualityBand;

function getReviewerVerdict(s: Startup): ReviewerVerdictBand | null {
  return getReviewerQualityBand(s.review);
}

/** Same footprint as DecisionBadge (type-label-tab, py-1 px-2, border) for grid pills. */
const WORK_GRID_PILL_BASE =
  'inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none type-label-tab py-1 px-2 uppercase shadow-none';

/** Selects: hairline bottom border only (toolbar chrome). */
const FILTER_SELECT_CLASS =
  'h-7 min-w-0 flex-1 cursor-pointer rounded-none border-0 border-b border-hairline-strong bg-transparent py-0.5 pl-0 pr-1 text-[11px] leading-tight text-oxford outline-none focus:border-field-border-strong';

/** Text actions on the filter toolbar — same border-b language as Source segment buttons (not text-underline). */
const FILTER_TOOLBAR_BORDER_BTN_BASE =
  `min-h-7 shrink-0 px-1.5 py-0.5 ${UI_FILTER_SEGMENT_INACTIVE} btn-interaction border-0 border-b bg-transparent`;

const SOURCE_SEGMENTS: { value: SourceFilter; label: string }[] = [
  { value: 'ALL', label: 'All' },
  { value: 'SCOUT', label: 'Scout' },
  { value: 'LOOKUP', label: 'Lookup' },
];

function getSourceBadge(startup: Startup): 'LOOKUP' | 'SCOUT' {
  return (startup.scout.origin_type ?? '').toLowerCase() === 'on_demand_lookup' ? 'LOOKUP' : 'SCOUT';
}

interface WorkGridProps {
  startups: Startup[];
  onStartupClick: (startup: Startup) => void;
  selectedId?: string | null;
  watchlistIds?: Set<string>;
}

function sortKey(s: Startup): string {
  return s.timestamps?.partnered_at ?? s.timestamps?.reviewed_at ?? s.timestamps?.discovered_at ?? '';
}

function getDecisionFilterValue(s: Startup): Exclude<DecisionFilter, 'ALL'> {
  if (s.partner?.human_review_required) return 'ESCALATION';
  const decision = s.partner?.decision;
  if (decision === 'YES') return 'YES';
  if (decision === 'NO' || decision === 'PASS') return 'NO';
  if (decision === 'MAYBE' || decision === 'WATCH') return 'MAYBE';
  if (s.review) return 'UNDECIDED';
  return 'AWAITING_REVIEW';
}

type FundingStageTier = 'pre-seed' | 'seed' | 'series-a' | 'series-b' | 'series-c-plus';

function getFundingStageTier(raw: string): FundingStageTier | null {
  const s = raw.trim().toLowerCase();
  if (!s) return null;
  const compact = s.replace(/[\s-]+/g, '');
  if (compact.includes('preseed') || /\bpre[-\s]?seed\b/i.test(raw)) return 'pre-seed';
  const seriesLetterMatch = raw.match(/series\s*([a-z])\b/i);
  if (seriesLetterMatch) {
    const letter = seriesLetterMatch[1].toUpperCase();
    if (letter >= 'C' && letter <= 'Z') return 'series-c-plus';
    if (letter === 'B') return 'series-b';
    if (letter === 'A') return 'series-a';
  }
  if (!/pre/.test(compact) && (/^seed$/i.test(s) || /^\s*seed\s*$/i.test(s))) return 'seed';
  return null;
}

function getFundingStageBadgeLabel(tier: FundingStageTier, raw: string): string {
  switch (tier) {
    case 'pre-seed':
      return 'PRE-SEED';
    case 'seed':
      return 'SEED';
    case 'series-a':
      return 'SERIES A';
    case 'series-b':
      return 'SERIES B';
    case 'series-c-plus':
      return raw.trim().toUpperCase();
  }
}

const FUNDING_STAGE_BADGE_CLASS: Record<FundingStageTier, string> = {
  'pre-seed': 'text-oxford/[0.30] border-oxford/[0.15]',
  seed: 'text-oxford/[0.50] border-oxford/[0.25]',
  'series-a': 'text-oxford/[0.75] border-oxford/[0.40]',
  'series-b': 'text-oxford/[0.90] border-oxford/[0.55]',
  'series-c-plus': 'text-oxford border-oxford/[0.70]',
};

function getDecisionBadgeVariant(s: Startup): 'YES' | 'NO' | 'MAYBE' | 'awaiting' | 'undecided' | 'escalation' {
  if (s.partner != null && s.partner.human_review_required === true) return 'escalation';
  const d = s.partner?.decision;
  if (!d) return s.review ? 'undecided' : 'awaiting';
  if (d === 'YES') return 'YES';
  if (d === 'NO' || d === 'PASS') return 'NO';
  return 'MAYBE';
}

/** Partner economic decision only (YES/NO/MAYBE variants), or null if no partner decision recorded. */
function getPartnerEconomicBadgeVariant(s: Startup): 'YES' | 'NO' | 'MAYBE' | null {
  const d = s.partner?.decision;
  if (d == null) return null;
  if (d === 'YES') return 'YES';
  if (d === 'NO' || d === 'PASS') return 'NO';
  return 'MAYBE';
}

type DecisionBadgeKind = ReturnType<typeof getDecisionBadgeVariant>;

function isPartnerEconomicDecisionBadge(v: DecisionBadgeKind): v is 'YES' | 'NO' | 'MAYBE' {
  return v === 'YES' || v === 'NO' || v === 'MAYBE';
}

/** Awaiting review, awaiting decision, or human review — shown below economic/verdict badges. */
function isWorkflowQueueBadge(v: DecisionBadgeKind): boolean {
  return v === 'awaiting' || v === 'undecided' || v === 'escalation';
}

const WorkGrid = ({ startups, onStartupClick, selectedId, watchlistIds: _watchlistIds }: WorkGridProps): JSX.Element => {
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('ALL');
  const [decisionFilter, setDecisionFilter] = useState<DecisionFilter>('ALL');
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>('ALL');
  const [sortFilter, setSortFilter] = useState<SortFilter>('NEWEST');
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  /** Opacity fade on filter change only (not on first paint). */
  const [listFilterFadeEnabled, setListFilterFadeEnabled] = useState(false);
  const reduceMotion = usePrefersReducedMotion();

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

  const hasActiveAdvancedFilters = decisionFilter !== 'ALL' || reviewFilter !== 'ALL';

  const [showCoachMark, setShowCoachMark] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined' || startups.length === 0) return;
    try {
      if (!window.localStorage.getItem(ORIENT_DISMISSED_KEY)) setShowCoachMark(true);
    } catch {
      /* ignore */
    }
  }, [startups.length]);

  useEffect(() => {
    if (!showCoachMark) return;
    const t = window.setTimeout(() => {
      try {
        window.localStorage.setItem(ORIENT_DISMISSED_KEY, '1');
      } catch {
        /* ignore */
      }
      setShowCoachMark(false);
    }, COACH_MARK_DURATION_MS);
    return () => clearTimeout(t);
  }, [showCoachMark]);

  const handleStartupClick = useCallback(
    (startup: Startup) => {
      if (showCoachMark) {
        try {
          window.localStorage.setItem(ORIENT_DISMISSED_KEY, '1');
        } catch {
          /* ignore */
        }
        setShowCoachMark(false);
      }
      onStartupClick(startup);
    },
    [onStartupClick, showCoachMark]
  );

  if (startups.length === 0) {
    return (
      <div className="w-full h-full min-h-[12rem] flex flex-col items-center justify-center border-b border-hairline">
        <EmptyState
          label="Pipeline"
          body="Scouts are filling the queue. First companies usually appear within a few minutes."
        />
      </div>
    );
  }

  return (
    <div className="w-full">
      <div
        className="sticky top-0 z-10 border-b border-hairline bg-paper px-3 py-1.5"
        role="toolbar"
        aria-label="Filter pipeline"
      >
        {/* Below lg: two rows (source | sort+link) so nothing collides beside the memo. lg+: one row. */}
        <div className="relative">
          <div className="flex min-w-0 flex-col gap-1.5 sm:pr-[5.5rem] lg:flex-row lg:flex-nowrap lg:items-end lg:gap-x-4 lg:pr-24">
            <div className="flex w-full min-w-0 items-center justify-between gap-2 lg:w-auto lg:shrink-0 lg:justify-start">
              <div className="flex min-w-0 items-center gap-2">
                <span className={`shrink-0 ${UI_FILTER_TOOLBAR_LABEL}`}>Source</span>
                <div
                  className="flex min-w-0 flex-1 items-center gap-0 sm:gap-0.5 lg:flex-initial"
                  role="group"
                  aria-label="Filter by source"
                >
                  {SOURCE_SEGMENTS.map(({ value, label }) => {
                    const active = sourceFilter === value;
                    return (
                      <button
                        key={value}
                        type="button"
                        onClick={() => {
                          setListFilterFadeEnabled(true);
                          setSourceFilter(value);
                        }}
                        className={`min-h-7 shrink-0 px-1.5 py-0.5 ${UI_FILTER_SEGMENT_INACTIVE} btn-interaction border-0 border-b bg-transparent ${
                          active
                            ? 'border-oxford/45 text-oxford'
                            : 'border-transparent text-oxford/42 hover:border-oxford/20 hover:text-oxford/75'
                        }`}
                        aria-pressed={active}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
              </div>
              <span
                className="shrink-0 font-mono text-[10px] uppercase tracking-[0.1em] text-oxford/45 tabular-nums sm:hidden"
                title={`${ordered.length} results after filters`}
                aria-label={`${ordered.length} results after filters`}
              >
                {ordered.length}
              </span>
            </div>
            <div className="flex w-full min-w-0 items-end gap-x-3 lg:flex-1 lg:min-w-0">
              <label className="flex min-w-0 flex-1 items-center gap-2 lg:max-w-[14rem] xl:max-w-[18rem]">
                <span className={`shrink-0 ${UI_FILTER_TOOLBAR_LABEL}`}>Sort</span>
                <select
                  value={sortFilter}
                  onChange={(e: ChangeEvent<HTMLSelectElement>) => {
                    setListFilterFadeEnabled(true);
                    setSortFilter(e.target.value as SortFilter);
                  }}
                  className={FILTER_SELECT_CLASS}
                >
                  <option value="NEWEST">Newest</option>
                  <option value="OLDEST">Oldest</option>
                  <option value="CONFIDENCE_HIGH">Confidence high to low</option>
                  <option value="CONFIDENCE_LOW">Confidence low to high</option>
                  <option value="NAME_AZ">Name A-Z</option>
                </select>
              </label>
              <button
                type="button"
                className={`${FILTER_TOOLBAR_BORDER_BTN_BASE} self-end text-left ${
                  showAdvancedFilters
                    ? 'border-oxford/45 text-oxford'
                    : 'border-transparent text-oxford/42 hover:border-oxford/20 hover:text-oxford/75'
                }`}
                onClick={() => setShowAdvancedFilters((v) => !v)}
                aria-expanded={showAdvancedFilters}
              >
                {showAdvancedFilters ? 'Fewer filters' : 'More filters'}
              </button>
            </div>
          </div>
          <div
            className="pointer-events-none absolute right-0 top-1/2 hidden -translate-y-1/2 font-mono text-[10px] uppercase tracking-[0.1em] text-oxford/40 tabular-nums sm:block"
            aria-label={`${ordered.length} results after filters`}
          >
            {ordered.length} results
          </div>
        </div>
        {showAdvancedFilters && (
          <div className="mt-1.5 flex flex-col gap-1.5 border-t border-hairline pt-1.5 sm:flex-row sm:flex-wrap sm:items-end sm:gap-x-5 sm:gap-y-1">
            <label className="flex min-w-0 flex-1 items-center gap-2 sm:max-w-[12rem] sm:flex-none">
              <span className={`shrink-0 ${UI_FILTER_TOOLBAR_LABEL}`}>Decision</span>
              <select
                value={decisionFilter}
                onChange={(e: ChangeEvent<HTMLSelectElement>) => {
                  setListFilterFadeEnabled(true);
                  setDecisionFilter(e.target.value as DecisionFilter);
                }}
                className={FILTER_SELECT_CLASS}
              >
                <option value="ALL">All</option>
                <option value="YES">Yes</option>
                <option value="NO">No</option>
                <option value="MAYBE">Maybe</option>
                <option value="ESCALATION">Escalation</option>
                <option value="UNDECIDED">Undecided</option>
                <option value="AWAITING_REVIEW">Awaiting review</option>
              </select>
            </label>
            <label className="flex min-w-0 flex-1 items-center gap-2 sm:max-w-[12rem] sm:flex-none">
              <span className={`shrink-0 ${UI_FILTER_TOOLBAR_LABEL}`}>Review</span>
              <select
                value={reviewFilter}
                onChange={(e: ChangeEvent<HTMLSelectElement>) => {
                  setListFilterFadeEnabled(true);
                  setReviewFilter(e.target.value as ReviewFilter);
                }}
                className={FILTER_SELECT_CLASS}
              >
                <option value="ALL">All</option>
                <option value="STRONG">Strong</option>
                <option value="MEDIUM">Medium</option>
                <option value="WEAK">Weak</option>
                <option value="UNREVIEWED">Unreviewed</option>
              </select>
            </label>
            <button
              type="button"
              className={`${FILTER_TOOLBAR_BORDER_BTN_BASE} self-start border-transparent text-oxford/42 hover:border-oxford/20 hover:text-oxford/75 sm:self-auto disabled:cursor-not-allowed disabled:border-transparent disabled:opacity-35 disabled:hover:border-transparent disabled:hover:text-oxford/25 disabled:text-oxford/25`}
              onClick={() => {
                setListFilterFadeEnabled(true);
                setDecisionFilter('ALL');
                setReviewFilter('ALL');
                setSourceFilter('ALL');
                setSortFilter('NEWEST');
              }}
              disabled={!hasActiveAdvancedFilters && sourceFilter === 'ALL' && sortFilter === 'NEWEST'}
            >
              Reset
            </button>
          </div>
        )}
      </div>

      <motion.div
        key={`${sourceFilter}-${decisionFilter}-${reviewFilter}-${sortFilter}`}
        className="w-full"
        initial={{ opacity: listFilterFadeEnabled ? 0 : 1 }}
        animate={{ opacity: 1 }}
        transition={transitionOrReduced(reduceMotion, {
          duration: listFilterFadeEnabled ? 0.15 : 0,
          ease: tokens.motion.ease,
        })}
      >
      {ordered.map((startup, index) => {
        const isSelected = selectedId != null && startup.id === selectedId;
        const hasDisagreement = startup.review?.reviewer_disagreement === true;
        const confidence = startup.scout.confidence;
        const sectorTrim = startup.scout.sector?.trim() ?? '';
        const fundingStageRaw = startup.scout.funding_stage?.trim() ?? '';
        const fundingTier = fundingStageRaw ? getFundingStageTier(fundingStageRaw) : null;
        const badgeVariant = getDecisionBadgeVariant(startup);
        const economicBadgeVariant = getPartnerEconomicBadgeVariant(startup);
        const showPartnerDecisionPlusEscalation =
          badgeVariant === 'escalation' && economicBadgeVariant != null;
        const showBottomWorkflowBadges =
          showPartnerDecisionPlusEscalation || isWorkflowQueueBadge(badgeVariant);
        const reviewBand = getReviewerVerdict(startup);

        return (
          <motion.div
            key={startup.id}
            role="button"
            tabIndex={0}
            aria-label={`View ${startup.scout.name}`}
            aria-current={isSelected ? 'true' : undefined}
            initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={transitionOrReduced(reduceMotion, {
              duration: tokens.motion.duration.short,
              delay: Math.min(index, 10) * 0.02,
              ease: tokens.motion.ease,
            })}
            className={`group cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-oxford/25 focus-visible:ring-inset btn-interaction transition-colors rounded-none overflow-hidden ${
              isSelected ? 'bg-registerTint' : 'bg-transparent hover:bg-registerTint'
            }${hasDisagreement ? ' border-l-2 border-l-oxford/40' : ''}`}
            onClick={() => handleStartupClick(startup)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleStartupClick(startup); }
            }}
          >
            {/* Single column on mobile/tablet; two columns (60/40) only from lg up */}
            <div className="flex flex-col gap-2 py-3 px-3 sm:px-4 lg:px-6 lg:grid lg:grid-cols-[3fr_2fr] lg:items-start lg:gap-4 border-b border-hairline">
              <div className="min-w-0 overflow-hidden">
                <div className="flex items-center gap-2 min-w-0">
                  {badgeVariant === 'escalation' && !isSelected && (
                    <span
                      className="w-1.5 h-1.5 shrink-0 rounded-none bg-escalation escalation-dot-active"
                      aria-hidden
                    />
                  )}
                  <h2
                    className="min-w-0 flex-1 truncate text-[15px] font-medium leading-[1.5] tracking-tight text-oxford/90"
                    style={{ fontFamily: '"Geist Sans", system-ui, sans-serif' }}
                  >
                    {startup.scout.name}
                  </h2>
                  {hasDisagreement && (
                    <span className="type-label-section text-oxford/40 shrink-0">contested</span>
                  )}
                </div>
                {startup.scout.one_line?.trim() ? (
                  <p
                    className={`min-w-0 text-[12px] leading-[1.6] text-oxford/50 overflow-hidden transition-[opacity,max-height,margin-top] ease-out ${
                      reduceMotion ? 'duration-0' : 'duration-150'
                    } ${
                      isSelected
                        ? 'mt-1 max-h-[200px] opacity-100'
                        : 'mt-0 max-h-0 opacity-0 group-hover:mt-1 group-hover:max-h-[200px] group-hover:opacity-100'
                    }`}
                    style={{ fontFamily: '"Geist Sans", system-ui, sans-serif' }}
                  >
                    {startup.scout.one_line.trim()}
                  </p>
                ) : null}
                <div className="mt-1 flex w-full max-w-full flex-nowrap items-center gap-x-2 overflow-x-auto no-scrollbar font-mono text-[10px] leading-[1.5] text-oxford/40">
                  {sectorTrim ? (
                    <span className="shrink-0 whitespace-nowrap uppercase">{sectorTrim}</span>
                  ) : null}
                  {sectorTrim && confidence != null ? (
                    <span className="shrink-0 text-oxford/25 select-none" aria-hidden>
                      ·
                    </span>
                  ) : null}
                  {confidence != null ? (
                    <span className="shrink-0 tabular-nums whitespace-nowrap">
                      {Math.round(confidence * 100)}%
                    </span>
                  ) : null}
                </div>
              </div>
              <div className="pt-2 border-t border-hairline flex flex-col items-start gap-1.5 min-w-0 lg:pt-1 lg:border-t-0 lg:text-right lg:items-end lg:justify-self-end">
                <span
                  className={`type-label-tab text-oxford/40 min-h-[1.25rem] flex items-center justify-end w-full transition-opacity ease-out ${
                    reduceMotion ? 'duration-0' : 'duration-150'
                  } ${
                    isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
                  }`}
                  aria-hidden
                >
                  → memo
                </span>
                <div className="flex w-full max-w-full min-w-0 flex-col gap-1.5 lg:items-end">
                  {fundingTier ? (
                    <span
                      className={`inline-flex w-fit max-w-full shrink-0 items-center rounded-none border border-solid py-[3px] px-[6px] font-mono text-[10px] font-normal uppercase leading-[1.5] tracking-[0.1em] ${FUNDING_STAGE_BADGE_CLASS[fundingTier]}`}
                    >
                      {getFundingStageBadgeLabel(fundingTier, fundingStageRaw)}
                    </span>
                  ) : null}
                  <div className="flex w-full min-w-0 max-w-full flex-col gap-1.5 lg:items-end">
                    {/* Source, verdict, partner economic — workflow queue badges on second row */}
                    <div className="flex min-w-0 w-full max-w-full flex-row flex-wrap items-center gap-1.5 justify-start sm:justify-end">
                      <span
                        className={`${WORK_GRID_PILL_BASE} ${
                          getSourceBadge(startup) === 'LOOKUP'
                            ? 'bg-lookup-surface text-lookup-ink'
                            : 'border border-solid border-field-border bg-transparent text-oxford/55'
                        }`}
                      >
                        {getSourceBadge(startup) === 'LOOKUP' ? 'LOOKUP' : 'SCOUT'}
                      </span>
                      {reviewBand ? <VerdictBandBadge band={reviewBand} /> : null}
                      {showPartnerDecisionPlusEscalation ? (
                        <DecisionBadge variant={economicBadgeVariant!} />
                      ) : isPartnerEconomicDecisionBadge(badgeVariant) ? (
                        <DecisionBadge variant={badgeVariant} />
                      ) : null}
                    </div>
                    {showBottomWorkflowBadges ? (
                      <div className="flex min-w-0 w-full max-w-full flex-row flex-wrap items-center gap-1.5 justify-start sm:justify-end">
                        {showPartnerDecisionPlusEscalation ? (
                          <DecisionBadge variant="escalation" />
                        ) : (
                          <DecisionBadge variant={badgeVariant} />
                        )}
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            </div>
            {index === 0 && showCoachMark && (
              <p className="type-label-tab text-oxford/25 mt-1 pb-2">Click to open memo</p>
            )}
          </motion.div>
        );
      })}
      </motion.div>
    </div>
  );
};

export default WorkGrid;
