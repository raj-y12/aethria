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
 *   • `partner.recommendation`: 'INVEST' | 'PASS' | 'MONITOR'
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
  'inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none type-label-tab py-0.5 px-1.5 lg:py-1 lg:px-2 uppercase shadow-none';

/** Selects: hairline bottom border only (toolbar chrome). */
const FILTER_SELECT_CLASS =
  'h-6 sm:h-7 min-w-0 sm:flex-1 cursor-pointer rounded-none border-0 border-b border-hairline bg-transparent py-0 sm:py-0.5 pl-0 pr-1 type-label-section text-oxford/60 outline-none focus:border-field-border-strong';

/** Text actions on the filter toolbar — same border-b language as Source segment buttons (not text-underline). */
const FILTER_TOOLBAR_BORDER_BTN_BASE =
  `min-h-6 sm:min-h-7 shrink-0 px-1.5 py-0.5 ${UI_FILTER_SEGMENT_INACTIVE} btn-interaction border-0 border-b bg-transparent`;

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
  const rec = s.partner?.recommendation;
  if (rec === 'INVEST') return 'YES';
  if (rec === 'PASS') return 'NO';
  if (rec === 'MONITOR') return 'MAYBE';
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
  'pre-seed': 'text-oxford/25 border-hairline',
  seed: 'text-oxford/40 border-oxford/25',
  'series-a': 'text-oxford/80 border-oxford/40',
  'series-b': 'text-oxford/80 border-oxford/60',
  'series-c-plus': 'text-oxford border-oxford/60',
};

function getDecisionBadgeVariant(s: Startup): 'INVEST' | 'PASS' | 'MONITOR' | 'awaiting' | 'undecided' | 'escalation' {
  if (s.partner != null && s.partner.human_review_required === true) return 'escalation';
  const rec = s.partner?.recommendation;
  if (!rec) return s.review ? 'undecided' : 'awaiting';
  if (rec === 'INVEST') return 'INVEST';
  if (rec === 'PASS') return 'PASS';
  return 'MONITOR';
}

/** Partner economic decision only (INVEST/PASS/MONITOR variants), or null if no partner decision recorded. */
function getPartnerEconomicBadgeVariant(s: Startup): 'INVEST' | 'PASS' | 'MONITOR' | null {
  const rec = s.partner?.recommendation;
  if (rec == null) return null;
  if (rec === 'INVEST') return 'INVEST';
  if (rec === 'PASS') return 'PASS';
  return 'MONITOR';
}

type DecisionBadgeKind = ReturnType<typeof getDecisionBadgeVariant>;

function isPartnerEconomicDecisionBadge(v: DecisionBadgeKind): v is 'INVEST' | 'PASS' | 'MONITOR' {
  return v === 'INVEST' || v === 'PASS' || v === 'MONITOR';
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
      <div className="w-full h-full min-h-[12rem] flex flex-col items-center justify-center">
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
        className="sticky top-0 z-10 border-b border-hairline bg-paper px-1 py-1.5 lg:px-phi-3 lg:py-phi-3"
        role="toolbar"
        aria-label="Filter pipeline"
      >
        {/* Below lg: two rows (source | sort+link) so nothing collides beside the memo. lg+: one row. */}
        <div className="relative">
          <div className="flex min-w-0 flex-row items-center gap-x-2 sm:flex-col sm:gap-phi-3 sm:pr-[5.5rem] lg:flex-row lg:flex-nowrap lg:items-end lg:gap-x-phi-5 lg:pr-24">
            {/* Source segments */}
            <div className="flex min-w-0 items-center gap-phi-2 sm:w-full sm:justify-between sm:gap-phi-3 lg:w-auto lg:shrink-0 lg:justify-start">
              <div className="flex min-w-0 items-center gap-phi-2 sm:gap-phi-3">
                <span className={`hidden sm:inline-block shrink-0 ${UI_FILTER_TOOLBAR_LABEL}`}>Source</span>
                <div
                  className="flex min-w-0 items-center gap-1 lg:flex-initial"
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
                        className={`min-h-6 sm:min-h-7 shrink-0 px-1 sm:px-1.5 py-0.5 ${UI_FILTER_SEGMENT_INACTIVE} btn-interaction border-0 border-b bg-transparent transition-[border-color,color] ${
                          active
                            ? 'border-oxford text-oxford'
                            : 'border-transparent text-oxford/40 hover:border-oxford/40 hover:text-oxford/80'
                        }`}
                        aria-pressed={active}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Sort + toggles */}
            <div className="flex min-w-0 flex-1 items-center gap-x-1.5 sm:w-full sm:items-end sm:gap-x-phi-4 lg:flex-1 lg:min-w-0">
              <label className="flex min-w-0 items-center gap-phi-2 sm:flex-1 sm:gap-phi-3 lg:max-w-[14rem] xl:max-w-[18rem]">
                <span className={`hidden sm:inline-block shrink-0 ${UI_FILTER_TOOLBAR_LABEL}`}>Sort</span>
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
                  <option value="CONFIDENCE_HIGH">Confidence ↓</option>
                  <option value="CONFIDENCE_LOW">Confidence ↑</option>
                  <option value="NAME_AZ">Name A–Z</option>
                </select>
              </label>
              <button
                type="button"
                className={`${FILTER_TOOLBAR_BORDER_BTN_BASE} shrink-0 transition-[border-color,color] ${
                  showAdvancedFilters
                    ? 'border-oxford text-oxford'
                    : 'border-transparent text-oxford/40 hover:border-oxford/40 hover:text-oxford/80'
                }`}
                onClick={() => setShowAdvancedFilters((v) => !v)}
                aria-expanded={showAdvancedFilters}
              >
                <span className="sm:hidden">{showAdvancedFilters ? 'Fewer' : 'More'}</span>
                <span className="hidden sm:inline">{showAdvancedFilters ? 'Fewer' : 'More'}</span>
              </button>
              {/* Count — mobile only, sits at the far right */}
              <span
                className="ml-auto shrink-0 type-meta tracking-badge uppercase text-oxford/40 tabular-nums sm:hidden"
                aria-label={`${ordered.length} results`}
              >
                {ordered.length}
              </span>
            </div>
          </div>
          <div
            className="pointer-events-none absolute right-0 top-1/2 hidden -translate-y-1/2 type-label-section text-oxford/40 tabular-nums sm:block"
            aria-label={`${ordered.length} results after filters`}
          >
            {ordered.length} results
          </div>
        </div>
        {showAdvancedFilters && (
          <div className="mt-phi-3 flex flex-col gap-phi-3 pt-phi-3 border-t border-oxford/[0.06] sm:flex-row sm:flex-wrap sm:items-end sm:gap-x-phi-5 sm:gap-y-phi-2">
            <label className="flex min-w-0 flex-1 items-center gap-phi-3 sm:max-w-[12rem] sm:flex-none">
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
            <label className="flex min-w-0 flex-1 items-center gap-phi-3 sm:max-w-[12rem] sm:flex-none">
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
              className={`${FILTER_TOOLBAR_BORDER_BTN_BASE} self-start border-transparent text-oxford/40 hover:border-oxford/20 hover:text-oxford/70 sm:self-auto disabled:cursor-not-allowed disabled:border-transparent disabled:opacity-30 disabled:hover:border-transparent disabled:hover:text-oxford/25 disabled:text-oxford/25`}
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
            initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={transitionOrReduced(reduceMotion, {
              duration: tokens.motion.duration.medium,
              delay: Math.min(index, 12) * 0.035,
              ease: tokens.motion.ease,
            })}
            className={`group cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-oxford/25 focus-visible:ring-inset btn-interaction transition-colors rounded-none overflow-hidden border-b border-hairline ${
              isSelected ? 'bg-registerTint' : 'bg-transparent hover:bg-registerTint'
            }${hasDisagreement ? ' border-l border-l-oxford/40' : ''}`}
            onClick={() => handleStartupClick(startup)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleStartupClick(startup); }
            }}
          >
            {/* Single column on mobile/tablet; two columns (60/40) only from lg up */}
            <div className="flex flex-col gap-phi-3 px-phi-4 py-phi-3 lg:grid lg:grid-cols-[3fr_2fr] lg:gap-phi-5 lg:px-phi-6 lg:py-phi-5 lg:items-start">
              <div className="min-w-0 overflow-hidden">
                <div className="flex items-center gap-phi-2 min-w-0">
                  {badgeVariant === 'escalation' && !isSelected && (
                    <span
                      className="w-1.5 h-1.5 shrink-0 rounded-none bg-escalation escalation-dot-active"
                      aria-hidden
                    />
                  )}
                  <h2
                    className="min-w-0 flex-1 truncate type-body font-semibold tracking-tight text-oxford"
                  >
                    {startup.scout.name}
                  </h2>
                  {hasDisagreement && (
                    <span className="type-label-section text-oxford/40 shrink-0">contested</span>
                  )}
                </div>
                {startup.scout.one_line?.trim() ? (
                  <p
                    className={`min-w-0 type-body-sm leading-phi text-oxford/60 overflow-hidden transition-[opacity,max-height,margin-top] ease-out ${
                      reduceMotion ? 'duration-0' : 'duration-200'
                    } ${
                      isSelected
                        ? 'mt-phi-3 max-h-[200px] opacity-100'
                        : 'mt-0 max-h-0 opacity-0 group-hover:mt-phi-3 group-hover:max-h-[200px] group-hover:opacity-100'
                    }`}
                  >
                    {startup.scout.one_line.trim()}
                  </p>
                ) : null}
                <div className="mt-phi-3 flex w-full max-w-full flex-nowrap items-center gap-x-phi-3 overflow-x-auto no-scrollbar type-meta tracking-badge text-oxford/40">
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
              <div className="min-w-0 flex flex-col items-start gap-phi-3 lg:justify-self-end lg:items-end lg:text-right">
                <span
                  className={`type-meta tracking-tab uppercase text-oxford/40 min-h-[1.25rem] flex items-center justify-end w-full transition-opacity ease-out ${
                    reduceMotion ? 'duration-0' : 'duration-150'
                  } ${
                    isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
                  }`}
                  aria-hidden
                >
                  open memo →
                </span>
                <div className="flex w-full max-w-full min-w-0 flex-col gap-phi-3 lg:items-end">
                  {fundingTier ? (
                    <span
                      className={`inline-flex w-fit max-w-full shrink-0 items-center rounded-none border py-phi-1 px-phi-2 type-meta tracking-badge uppercase ${FUNDING_STAGE_BADGE_CLASS[fundingTier]}`}
                    >
                      {getFundingStageBadgeLabel(fundingTier, fundingStageRaw)}
                    </span>
                  ) : null}
                  <div className="flex w-full min-w-0 max-w-full flex-col gap-phi-2 lg:items-end">
                    {/* Source, verdict, partner economic — workflow queue badges on second row */}
                    <div className="flex min-w-0 w-full max-w-full flex-row flex-wrap items-center gap-phi-2 justify-start sm:justify-end">
                      {getSourceBadge(startup) === 'LOOKUP' && (
                        <span className={`${WORK_GRID_PILL_BASE} bg-lookup-surface text-lookup-ink`}>
                          LOOKUP
                        </span>
                      )}
                      {reviewBand ? <VerdictBandBadge band={reviewBand} /> : null}
                      {showPartnerDecisionPlusEscalation ? (
                        <DecisionBadge variant={economicBadgeVariant!} />
                      ) : isPartnerEconomicDecisionBadge(badgeVariant) ? (
                        <DecisionBadge variant={badgeVariant} />
                      ) : null}
                    </div>
                    {showBottomWorkflowBadges ? (
                      <div className="flex min-w-0 w-full max-w-full flex-row flex-wrap items-center gap-phi-2 justify-start sm:justify-end">
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
              <p className="type-label-tab text-oxford/25 mt-phi-1 pb-phi-2">Click to open memo</p>
            )}
          </motion.div>
        );
      })}
      </motion.div>
    </div>
  );
};

export default WorkGrid;
