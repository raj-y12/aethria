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
 * Each row’s right column: inline reviewer pill (VerdictBadge) + DecisionBadge
 * for partner / pipeline state.
 */

import { useMemo, useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import type { Startup } from '../types/startup';
import { getReviewerQualityBand, type ReviewerQualityBand } from '../design-system/semantics';
import { tokens } from '../design-system/tokens';
import DecisionBadge from './DecisionBadge';
import EmptyState from './EmptyState';
import {
  PANEL_TAB_ACTIVE_CLASS,
  PANEL_TAB_BAR_CLASS,
  PANEL_TAB_BUTTON_CLASS,
  PANEL_TAB_INACTIVE_CLASS,
} from './PanelShell';

const ORIENT_DISMISSED_KEY = 'aethria_dashboard_orient_dismissed';
const COACH_MARK_DURATION_MS = 4000;

type ActiveFilter = 'ALL' | 'STRONG' | 'MEDIUM' | 'WEAK' | 'ESCALATIONS';

const FILTER_ITEMS: { id: ActiveFilter; label: string }[] = [
  { id: 'ALL', label: 'ALL' },
  { id: 'STRONG', label: 'STRONG' },
  { id: 'MEDIUM', label: 'MEDIUM' },
  { id: 'WEAK', label: 'WEAK' },
  { id: 'ESCALATIONS', label: 'ESCALATIONS' },
];

type ReviewerVerdictBand = ReviewerQualityBand;

function getReviewerVerdict(s: Startup): ReviewerVerdictBand | null {
  return getReviewerQualityBand(s.review);
}

/** Shared shell for reviewer + partner pills in this grid. */
const GRID_BADGE_SHELL =
  'inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none font-mono text-[9px] font-normal uppercase leading-[1.5] tracking-[0.1em] py-[3px] px-[6px]';

function VerdictBadge({ band }: { band: ReviewerVerdictBand }) {
  const tone =
    band === 'STRONG'
      ? 'bg-oxford text-paper'
      : band === 'MEDIUM'
        ? 'bg-oxford/50 text-paper'
        : 'bg-oxford/20 text-oxford';
  return (
    <span className={`${GRID_BADGE_SHELL} ${tone}`}>
      {band}
    </span>
  );
}

function filterStartupsByActive(list: Startup[], active: ActiveFilter): Startup[] {
  switch (active) {
    case 'ALL':
      return list;
    case 'STRONG':
      return list.filter((s) => getReviewerVerdict(s) === 'STRONG');
    case 'MEDIUM':
      return list.filter((s) => getReviewerVerdict(s) === 'MEDIUM');
    case 'WEAK':
      return list.filter((s) => getReviewerVerdict(s) === 'WEAK');
    case 'ESCALATIONS':
      return list.filter((s) => s.partner != null && s.partner.human_review_required === true);
    default:
      return list;
  }
}

interface WorkGridProps {
  startups: Startup[];
  onStartupClick: (startup: Startup) => void;
  selectedId?: string | null;
  watchlistIds?: Set<string>;
}

/** Queue / accent: partner flagged for human review (strict boolean `true` only). */
function isEscalation(s: Startup): boolean {
  return s.partner != null && s.partner.human_review_required === true;
}

function sortKey(s: Startup): string {
  return s.timestamps?.partnered_at ?? s.timestamps?.reviewed_at ?? s.timestamps?.discovered_at ?? '';
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

const WorkGrid = ({ startups, onStartupClick, selectedId, watchlistIds: _watchlistIds }: WorkGridProps): JSX.Element => {
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>('ALL');
  /** Opacity fade on filter change only (not on first paint). */
  const [listFilterFadeEnabled, setListFilterFadeEnabled] = useState(false);

  const filteredStartups = useMemo(
    () => filterStartupsByActive(startups, activeFilter),
    [startups, activeFilter]
  );

  const ordered = useMemo(() => {
    const escalations = filteredStartups.filter(isEscalation).sort((a, b) => sortKey(b).localeCompare(sortKey(a)));
    const decided = filteredStartups
      .filter((s) => s.partner?.decision != null && !isEscalation(s))
      .sort((a, b) => sortKey(b).localeCompare(sortKey(a)));
    const reviewedNoDecision = filteredStartups
      .filter((s) => s.review != null && !s.partner?.decision)
      .sort((a, b) => sortKey(b).localeCompare(sortKey(a)));
    const unreviewed = filteredStartups.filter((s) => s.review == null).sort((a, b) => sortKey(b).localeCompare(sortKey(a)));
    return [...escalations, ...decided, ...reviewedNoDecision, ...unreviewed];
  }, [filteredStartups]);

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
      <div className="w-full h-full min-h-[12rem] flex flex-col items-center justify-center border-b border-oxford/[0.06]">
        <EmptyState
          label="Pipeline"
          body="Scouts are filling the queue. First companies usually appear within a few minutes."
        />
      </div>
    );
  }

  return (
    <div className="w-full">
      <nav
        className={`sticky top-0 z-10 w-full flex-none min-w-0 shrink-0 overflow-x-auto no-scrollbar bg-paper ${PANEL_TAB_BAR_CLASS}`}
        role="toolbar"
        aria-label="Filter pipeline"
      >
        {FILTER_ITEMS.map(({ id, label }) => {
          const isActive = activeFilter === id;
          return (
            <button
              key={id}
              type="button"
              aria-selected={isActive}
              onClick={() => {
                setListFilterFadeEnabled(true);
                setActiveFilter(id);
              }}
              className={`shrink-0 ${PANEL_TAB_BUTTON_CLASS} ${
                isActive ? PANEL_TAB_ACTIVE_CLASS : PANEL_TAB_INACTIVE_CLASS
              }`}
            >
              {label}
            </button>
          );
        })}
      </nav>

      <motion.div
        key={activeFilter}
        className="w-full"
        initial={{ opacity: listFilterFadeEnabled ? 0 : 1 }}
        animate={{ opacity: 1 }}
        transition={{
          duration: listFilterFadeEnabled ? 0.15 : 0,
          ease: tokens.motion.ease,
        }}
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
        const reviewBand = getReviewerVerdict(startup);

        return (
          <motion.div
            key={startup.id}
            role="button"
            tabIndex={0}
            aria-label={`View ${startup.scout.name}`}
            aria-current={isSelected ? 'true' : undefined}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: tokens.motion.duration.short,
              delay: Math.min(index, 10) * 0.02,
              ease: tokens.motion.ease,
            }}
            className={`group cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-oxford/25 focus-visible:ring-inset btn-interaction transition-colors rounded-none overflow-hidden ${
              isSelected ? 'bg-registerTint' : 'bg-transparent hover:bg-registerTint'
            }${hasDisagreement ? ' border-l-2 border-l-oxford/40' : ''}`}
            onClick={() => handleStartupClick(startup)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleStartupClick(startup); }
            }}
          >
            {/* Single column on mobile/tablet; two columns (60/40) only from lg up */}
            <div className="flex flex-col gap-2 py-3 px-3 sm:px-4 lg:px-6 lg:grid lg:grid-cols-[3fr_2fr] lg:items-start lg:gap-4 border-b border-oxford/[0.06]">
              <div className="min-w-0 overflow-hidden">
                <div className="flex items-center gap-2 min-w-0">
                  {badgeVariant === 'escalation' && !isSelected && (
                    <span
                      className="w-1.5 h-1.5 shrink-0 rounded-none escalation-dot-active"
                      style={{ backgroundColor: 'var(--color-accent)' }}
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
                    className={`min-w-0 text-[12px] leading-[1.6] text-oxford/50 overflow-hidden transition-[opacity,max-height,margin-top] duration-150 ease-out ${
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
              <div className="pt-2 border-t border-oxford/[0.06] flex flex-col items-start gap-1.5 min-w-0 lg:pt-1 lg:border-t-0 lg:text-right lg:items-end lg:justify-self-end">
                <span
                  className="type-label-tab text-oxford/40 min-h-[1.25rem] flex items-center justify-end w-full opacity-0 group-hover:opacity-100"
                  style={{ transition: 'opacity 150ms var(--motion-ease, ease-out)' }}
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
                  {/* Single wrap row: verdict + partner + escalation stay inline on narrow viewports */}
                  <div className="flex min-w-0 w-full max-w-full flex-row flex-wrap items-center gap-1.5 justify-start sm:justify-end">
                    {reviewBand ? <VerdictBadge band={reviewBand} /> : null}
                    {showPartnerDecisionPlusEscalation ? (
                      <>
                        <DecisionBadge variant={economicBadgeVariant!} />
                        <DecisionBadge variant="escalation" />
                      </>
                    ) : (
                      <DecisionBadge variant={badgeVariant} />
                    )}
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
