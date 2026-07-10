/**
 * Queue attention driver — one dominant signal per row.
 *
 * Presentation model:
 * - Partner recommendation + pipeline state → filled DecisionBadge in QueueVerdictLine + conviction %
 * - Why look here (ruling, stale, evidence) → one filled QueueAttentionBadge
 *
 * List API limitations (do not invent fields):
 * - partner.confidence, decision_drivers, snapshot not on list projection
 * - thesis_alignment_* not on list; mandate conflict via adverse heuristics only
 * - no escalation_reason; use queue_reason + human_review_required
 * - use scout.sector (no category field)
 */
import type { Startup } from '../types/startup';
import type { QueueAnnotationVariant } from '../design-system/verdictBadgeTokens';
import { normalizeConfidence } from '../components/scoring/ConfidenceIndicator';
import { extractAdverseRegister, type AdverseRegisterItem } from './adverseRegister';
import { getDealAgeDays, isDealDecided, type RulingDecision } from './dealState';
import { computeConfiguredScore, isStartupStaleByConfig, type FundConfiguration } from './fundConfiguration';

export type QueueAttentionDriverKey =
  | 'reviewer_split'
  | 'needs_ruling'
  | 'stale'
  | 'missing_evidence'
  | 'mandate_conflict'
  | 'weak_conviction'
  | 'high_conviction'
  | 'execution_risk'
  | 'defensibility_concern'
  | 'ready'
  | 'awaiting_review'
  | 'on_monitor'
  | 'decided';

export type QueueAttentionTone = 'critical' | 'watch' | 'active' | 'quiet';

export interface QueueAttentionDriver {
  key: QueueAttentionDriverKey;
  label: string;
  detail?: string;
  tone: QueueAttentionTone;
}

export interface QueueRowContext {
  startup: Startup;
  adverseItems: AdverseRegisterItem[];
  configuredScore: number;
  isDecided: boolean;
  isStale: boolean;
  isEscalated: boolean;
  needsRuling: boolean;
  onMonitorList: boolean;
  ageDays: number | null;
  fundConfiguration: FundConfiguration;
}

const WEAK_CONVICTION_THRESHOLD = 45;
const HIGH_CONVICTION_THRESHOLD = 72;

export function getVisibleRecommendation(startup: Startup): 'INVEST' | 'PASS' | 'MONITOR' | null {
  const human = startup.human_resolution?.decision;
  if (human === 'YES') return 'INVEST';
  if (human === 'NO') return 'PASS';
  if (human === 'MAYBE') return 'MONITOR';
  return startup.partner?.recommendation ?? null;
}

export function startupNeedsRuling(startup: Startup): boolean {
  return !isDealDecided(startup) && Boolean(startup.review || startup.partner?.recommendation);
}

/** Conviction % for queue display — list-safe fallback chain. */
export function getQueueConvictionPct(ctx: QueueRowContext): number | null {
  const { startup, configuredScore } = ctx;
  // Conviction == the canonical overall SCORE (quality), consistent with the memo.
  // It is deliberately NOT partner.confidence: confidence (how sure the decision is)
  // is a separate axis and was previously conflated under the same "conviction" label
  // (audit B3). Returned on a 0–100 internal scale (score×10) for the tier thresholds;
  // display formats it back to x/10.
  const agg = startup.review?.overall_score ?? startup.review?.aggregate_score;
  if (typeof agg === 'number' && Number.isFinite(agg)) {
    return Math.round(agg <= 10 ? agg * 10 : agg);
  }

  if (Number.isFinite(configuredScore) && configuredScore > 0) return configuredScore;

  const scoutConf = normalizeConfidence(startup.scout.confidence);
  if (scoutConf != null) return Math.round(scoutConf * 100);

  return null;
}

/** Conviction on the canonical 0–10 scale (x.x), matching the memo. */
export function getQueueConvictionScore(ctx: QueueRowContext): number | null {
  const pct = getQueueConvictionPct(ctx);
  return pct == null ? null : pct / 10;
}

export function formatQueueConviction(ctx: QueueRowContext): string {
  const score = getQueueConvictionScore(ctx);
  return score == null ? '—' : `${score.toFixed(1)}/10`;
}

export type ConvictionTier = 'low' | 'mid' | 'high' | 'none';

export function getConvictionTier(pct: number | null): ConvictionTier {
  if (pct == null || !Number.isFinite(pct)) return 'none';
  if (pct < WEAK_CONVICTION_THRESHOLD) return 'low';
  if (pct < HIGH_CONVICTION_THRESHOLD) return 'mid';
  return 'high';
}

/** Queue docket — monochrome conviction (no tier colour ramp). */
export const QUEUE_CONVICTION_CLASS = {
  ambient: 'text-oxford/60 font-normal tabular-nums',
  prominent: 'text-oxford/60 font-normal tabular-nums',
} as const;

/** @deprecated Memo / rich UI only — queue uses QUEUE_CONVICTION_CLASS. */
export const CONVICTION_TIER_CLASS: Record<
  ConvictionTier,
  { ambient: string; prominent: string }
> = {
  none: { ambient: 'text-oxford/60 font-normal', prominent: 'text-oxford/60 font-normal' },
  low: { ambient: 'text-oxford/60 font-normal', prominent: 'text-oxford/60 font-normal' },
  mid: { ambient: 'text-oxford/[0.68] font-medium', prominent: 'text-oxford/[0.72] font-medium' },
  high: { ambient: 'text-oxford/[0.88] font-semibold', prominent: 'text-oxford font-semibold' },
};

/** Attention-worthy drivers that earn a badge — the "why look here" signal.
 *  Calm states (ready / awaiting_review / on_monitor / high_conviction / decided) do not. */
const ATTENTION_BADGE_KEYS: ReadonlySet<QueueAttentionDriverKey> = new Set([
  'needs_ruling',
  'stale',
  'missing_evidence',
  'mandate_conflict',
  'weak_conviction',
  'execution_risk',
  'defensibility_concern',
]);

export function shouldRenderAttentionBadge(driver: QueueAttentionDriver): boolean {
  return ATTENTION_BADGE_KEYS.has(driver.key);
}

export function shouldRenderAttentionQuietText(driver: QueueAttentionDriver): boolean {
  if (shouldRenderAttentionBadge(driver) || driver.key === 'decided') return false;
  return driver.key === 'ready' || driver.key === 'awaiting_review';
}

/** Calm queue copy for escalation interrupts — sentence case, no pill. */
export function attentionDriverQueueLabel(driver: QueueAttentionDriver): string | null {
  if (!shouldRenderAttentionBadge(driver)) return null;
  switch (driver.key) {
    case 'needs_ruling':
      return 'Needs ruling';
    case 'reviewer_split':
      return 'Reviewer split';
    default:
      return driver.label;
  }
}

/** Short scan label for annotation badge; null when no badge should render. */
export function attentionDriverBadgeLabel(
  driver: QueueAttentionDriver,
  ctx?: Pick<QueueRowContext, 'ageDays'>
): string | null {
  if (!shouldRenderAttentionBadge(driver)) return null;

  switch (driver.key) {
    case 'reviewer_split':
      return 'REVIEWER SPLIT';
    case 'needs_ruling':
      return 'NEEDS RULING';
    case 'stale':
      return ctx?.ageDays != null ? `STALE ${ctx.ageDays}D` : 'STALE';
    case 'missing_evidence':
      return 'LIMITED EVIDENCE';
    case 'mandate_conflict':
      return 'MANDATE CONFLICT';
    case 'weak_conviction':
      return 'WEAK CONVICTION';
    case 'high_conviction':
      return 'HIGH CONVICTION';
    case 'execution_risk':
      return 'EXECUTION RISK';
    case 'defensibility_concern':
      return 'DEFENSIBILITY';
    case 'on_monitor':
      return 'ON MONITOR';
    default:
      return driver.label.toUpperCase();
  }
}

/** Filled badge colour variant — burgundy interrupts harder than gold. */
export function attentionBadgeVariant(driver: QueueAttentionDriver): QueueAnnotationVariant {
  switch (driver.key) {
    case 'reviewer_split':
    case 'needs_ruling':
    case 'mandate_conflict':
      return 'burgundy';
    case 'missing_evidence':
    case 'weak_conviction':
    case 'stale':
    case 'execution_risk':
    case 'defensibility_concern':
      return 'gold';
    case 'high_conviction':
      return 'positive';
    default:
      return driver.tone === 'critical' ? 'burgundy' : 'gold';
  }
}

function cleanQueueReason(reason: string | null | undefined): string {
  const text = (reason ?? '').replace(/\s+/g, ' ').trim();
  if (!text) return '';
  if (/^human ruling required\.?$/i.test(text)) return '';
  if (/^partner recommends \w+\.?$/i.test(text)) return '';
  return text;
}

function mandateConflictItem(items: AdverseRegisterItem[]): AdverseRegisterItem | undefined {
  return items.find(
    (item) =>
      item.source?.toLowerCase().includes('thesis') ||
      item.title.toLowerCase().includes('mandate') ||
      item.title.toLowerCase().includes('thesis')
  );
}

function missingEvidenceItem(items: AdverseRegisterItem[]): AdverseRegisterItem | undefined {
  return items.find((item) => item.missingData || item.severity === 'high');
}

function riskDriverFromAdverse(item: AdverseRegisterItem): QueueAttentionDriver | null {
  const lower = `${item.title} ${item.source ?? ''}`.toLowerCase();
  if (lower.includes('defensib')) {
    return {
      key: 'defensibility_concern',
      label: `Defensibility concern · ${item.title}`,
      detail: item.whyItMatters,
      tone: 'watch',
    };
  }
  if (lower.includes('execution') || lower.includes('traction') || lower.includes('founder')) {
    return {
      key: 'execution_risk',
      label: `Execution risk · ${item.title}`,
      detail: item.whyItMatters,
      tone: 'watch',
    };
  }
  return null;
}

function humanDecisionLabel(decision: RulingDecision | null | undefined): string {
  if (decision === 'YES') return 'Invested';
  if (decision === 'NO') return 'Passed';
  return 'Monitoring';
}

export function resolveQueueAttentionDriver(ctx: QueueRowContext): QueueAttentionDriver {
  const { startup, adverseItems, isDecided, isStale, isEscalated, needsRuling, onMonitorList, ageDays } = ctx;
  const recommendation = getVisibleRecommendation(startup);
  const convictionPct = getQueueConvictionPct(ctx);

  if (isDecided) {
    const decision = startup.human_resolution?.decision;
    return {
      key: 'decided',
      label: `Ruled · ${humanDecisionLabel(decision)}`,
      detail: startup.human_resolution?.notes?.trim() || undefined,
      tone: 'quiet',
    };
  }

  if (isEscalated) {
    const reason =
      cleanQueueReason(startup.queue_reason) ||
      adverseItems[0]?.title ||
      startup.partner?.llm_fallback_reason?.trim() ||
      'Partner flagged for human judgment.';
    return {
      key: 'needs_ruling',
      label: 'Needs ruling',
      detail: reason,
      tone: 'critical',
    };
  }

  if (isStale && ageDays != null) {
    return {
      key: 'stale',
      label: `Stale · ${ageDays}d`,
      detail: cleanQueueReason(startup.queue_reason) || 'Unresolved beyond the configured stale threshold.',
      tone: 'watch',
    };
  }

  const missing = missingEvidenceItem(adverseItems);
  if (missing) {
    return {
      key: 'missing_evidence',
      label: `Missing evidence · ${missing.title}`,
      detail: missing.whyItMatters,
      tone: 'critical',
    };
  }

  const mandate = mandateConflictItem(adverseItems);
  if (mandate) {
    return {
      key: 'mandate_conflict',
      label: `Mandate conflict · ${mandate.title}`,
      detail: mandate.whyItMatters,
      tone: 'watch',
    };
  }

  if (recommendation && convictionPct != null && convictionPct < WEAK_CONVICTION_THRESHOLD) {
    return {
      key: 'weak_conviction',
      label: 'Weak conviction',
      detail:
        startup.partner?.decision_rationale?.trim() ||
        cleanQueueReason(startup.queue_reason) ||
        `System conviction at ${(convictionPct / 10).toFixed(1)}/10 with ${recommendation} recommendation.`,
      tone: 'watch',
    };
  }

  if (
    recommendation === 'INVEST' &&
    convictionPct != null &&
    convictionPct >= HIGH_CONVICTION_THRESHOLD &&
    !needsRuling
  ) {
    return {
      key: 'high_conviction',
      label: 'High conviction',
      detail:
        startup.review?.aethria_view?.thesis_fit_line?.trim() ||
        cleanQueueReason(startup.queue_reason) ||
        undefined,
      tone: 'active',
    };
  }

  const topAdverse = adverseItems[0];
  if (topAdverse && topAdverse.severity !== 'low') {
    const riskDriver = riskDriverFromAdverse(topAdverse);
    if (riskDriver) return riskDriver;
    return {
      key: topAdverse.severity === 'high' ? 'missing_evidence' : 'execution_risk',
      label: `${topAdverse.title}`,
      detail: topAdverse.whyItMatters,
      tone: topAdverse.severity === 'high' ? 'critical' : 'watch',
    };
  }

  if (onMonitorList && recommendation === 'MONITOR') {
    return {
      key: 'on_monitor',
      label: 'On monitor',
      detail: cleanQueueReason(startup.queue_reason) || startup.scout.one_line?.trim(),
      tone: 'active',
    };
  }

  if (needsRuling) {
    const detail =
      cleanQueueReason(startup.queue_reason) ||
      startup.partner?.decision_drivers?.[0]?.trim() ||
      startup.partner?.snapshot?.key_signal?.trim() ||
      (recommendation ? `Partner recommends ${recommendation.toLowerCase()}.` : undefined);
    return {
      key: 'ready',
      label: 'Ready for judgment',
      detail,
      tone: 'active',
    };
  }

  if (!startup.review) {
    return {
      key: 'awaiting_review',
      label: 'Awaiting review',
      detail:
        startup.scout.biggest_unknown?.trim() ||
        startup.scout.one_line?.trim() ||
        cleanQueueReason(startup.queue_reason) ||
        'Scout discovery queued for reviewer judgment.',
      tone: 'quiet',
    };
  }

  return {
    key: 'ready',
    label: 'In review',
    detail:
      startup.review.aethria_view?.focal_question?.trim() ||
      startup.review.overall_summary?.trim() ||
      cleanQueueReason(startup.queue_reason),
    tone: 'active',
  };
}

const LOW_SIGNAL_ONE_LINERS = new Set([
  'Human ruling recorded.',
  'Reviewer output is available.',
  'Review is complete and ready for judgment.',
  'Unresolved beyond the configured stale threshold.',
  'Scout discovery is queued for reviewer judgment.',
  'Human review required before conviction can form.',
  'Partner flagged for human judgment.',
  'Multiple reviewer verdicts diverge on this case.',
]);

const REDUNDANT_ROW_PHRASES = [
  /\bthesis[- ]aligned\b/gi,
  /\bhigh conviction\b/gi,
  /\brequires review\b/gi,
  /\bready for judgment\b/gi,
  /\breview is complete\b/gi,
  /\bhuman review required\b/gi,
];

function compactOneLiner(text: string): string {
  let out = text.replace(/\s+/g, ' ').trim();
  REDUNDANT_ROW_PHRASES.forEach((pattern) => {
    out = out.replace(pattern, '');
  });
  out = out
    .replace(/\s{2,}/g, ' ')
    .replace(/\s*[,;]\s*/g, ', ')
    .replace(/\s+\./g, '.')
    .trim()
    .replace(/^[,.;:\-]+/, '')
    .replace(/[,;:\-]+$/, '')
    .trim();
  return out;
}

export function rowSectorStageLine(startup: Startup): string {
  const sector = (startup.scout.sector || '').split('/')[0].trim();
  const fundingStage = startup.scout.funding_stage?.trim();
  const parts: string[] = [];
  if (sector) parts.push(sector);
  if (fundingStage && fundingStage.toLowerCase() !== 'unknown') parts.push(fundingStage);
  return parts.join(' · ');
}

export function rowQueueOneLiner(ctx: QueueRowContext, driver: QueueAttentionDriver): string | null {
  const { startup } = ctx;
  const candidates = [
    driver.detail?.trim(),
    cleanQueueReason(startup.queue_reason),
    startup.review?.aethria_view?.focal_question?.trim(),
    startup.scout.one_line?.trim(),
    startup.partner?.snapshot?.one_liner?.trim(),
    startup.review?.overall_summary?.trim(),
    startup.scout.biggest_unknown?.trim(),
  ].filter((value): value is string => Boolean(value));

  for (const candidate of candidates) {
    if (LOW_SIGNAL_ONE_LINERS.has(candidate)) continue;
    const compact = compactOneLiner(candidate);
    if (compact.length >= 24) return compact;
  }
  return null;
}

export function buildQueueRowContext(
  startup: Startup,
  fundConfiguration: FundConfiguration,
  options: {
    configuredScore: number;
    onMonitorList: boolean;
  }
): QueueRowContext {
  const adverseItems = extractAdverseRegister(startup);
  const isDecided = isDealDecided(startup);
  return {
    startup,
    adverseItems,
    configuredScore: options.configuredScore,
    isDecided,
    isStale: isStartupStaleByConfig(startup, fundConfiguration),
    isEscalated: Boolean(startup.partner?.human_review_required) && !isDecided,
    needsRuling: startupNeedsRuling(startup),
    onMonitorList: options.onMonitorList,
    ageDays: getDealAgeDays(startup),
    fundConfiguration,
  };
}

export function computeConfiguredScoreForStartup(startup: Startup, config: FundConfiguration): number {
  return computeConfiguredScore(startup, config);
}
