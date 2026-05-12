import type { Startup } from '../types/startup';
import { extractAdverseRegister } from './adverseRegister';

export type RulingDecision = 'YES' | 'NO' | 'MAYBE';
export type DealQueueState = 'decided' | 'escalated' | 'pending' | 'awaiting-review' | 'stale';

const STALE_DAYS = 7;
const DAY_MS = 24 * 60 * 60 * 1000;

export function decisionToPartnerRecommendation(decision: RulingDecision): 'INVEST' | 'PASS' | 'MONITOR' {
  if (decision === 'YES') return 'INVEST';
  if (decision === 'NO') return 'PASS';
  return 'MONITOR';
}

export function partnerRecommendationToDecision(
  recommendation: Startup['partner'] extends infer P
    ? P extends { recommendation?: infer R }
      ? R
      : never
    : never
): RulingDecision | null {
  if (recommendation === 'INVEST') return 'YES';
  if (recommendation === 'PASS') return 'NO';
  if (recommendation === 'MONITOR') return 'MAYBE';
  return null;
}

export function isDealHumanResolved(startup: Startup): boolean {
  return Boolean(startup.human_resolution?.resolved_at);
}

export function isDealDecided(startup: Startup): boolean {
  return isDealHumanResolved(startup);
}

/**
 * "Unresolved" = unreviewed OR undecided.
 *
 * Mirrors the server-side `unresolved_at` semantic from
 * `supabase/migrations/20260512000001_unresolved_state.sql`, but computed
 * client-side so the count is correct even if that column is missing or stale.
 *
 * A startup is unresolved when ANY of the following is true:
 *   1. No analyst review yet                              → "unreviewed"
 *   2. No partner recommendation yet                      → "undecided"
 *   3. Partner flagged for human review and no human ruling → "undecided (escalated)"
 */
export function isDealUnresolved(startup: Startup): boolean {
  if (isDealHumanResolved(startup)) return false;
  if (!startup.review) return true;
  if (!startup.partner?.recommendation) return true;
  if (startup.partner.human_review_required) return true;
  return false;
}

/** In queue, no analyst review yet (excludes human-resolved). */
export function isDealUnreviewed(startup: Startup): boolean {
  return !isDealHumanResolved(startup) && !startup.review;
}

/**
 * Review complete but partner recommendation not produced yet.
 * Escalations awaiting IC (human_review_required) are excluded — counted via escalations stat.
 */
export function isDealPendingPartnerDecision(startup: Startup): boolean {
  return (
    !isDealHumanResolved(startup) &&
    Boolean(startup.review) &&
    !startup.partner?.recommendation
  );
}

export function getDealLastActivityIso(startup: Startup): string {
  return startup.human_resolution?.resolved_at
    ?? startup.timestamps?.partnered_at
    ?? startup.timestamps?.reviewed_at
    ?? startup.timestamps?.discovered_at
    ?? '';
}

export function getDealAgeDays(startup: Startup, now = Date.now()): number | null {
  const raw = getDealLastActivityIso(startup);
  if (!raw) return null;
  const time = new Date(raw).getTime();
  if (!Number.isFinite(time)) return null;
  return Math.max(0, Math.floor((now - time) / DAY_MS));
}

export function isDealStale(startup: Startup, now = Date.now()): boolean {
  if (isDealDecided(startup)) return false;
  const age = getDealAgeDays(startup, now);
  return age != null && age >= STALE_DAYS;
}

export function getDealQueueState(startup: Startup, now = Date.now()): DealQueueState {
  if (isDealDecided(startup)) return 'decided';
  if (startup.partner?.human_review_required) return 'escalated';
  if (isDealStale(startup, now)) return 'stale';
  if (startup.review || startup.partner?.recommendation) return 'pending';
  return 'awaiting-review';
}

export function hasMeaningfulAdverseItems(startup: Startup): boolean {
  return extractAdverseRegister(startup).length > 0;
}

export function queueAttentionRank(startup: Startup, now = Date.now()): number {
  const adverse = extractAdverseRegister(startup);
  const high = adverse.some((item) => item.severity === 'high');
  if (isDealDecided(startup)) return 4;
  if (high || startup.partner?.human_review_required) return 0;
  if (isDealStale(startup, now)) return 1;
  if (startup.review) return 2;
  return 3;
}

export function buildOptimisticResolution(
  startup: Startup,
  decision: RulingDecision,
  notes: string
): Startup {
  const now = new Date().toISOString();
  const priorHistory = startup.conviction_state?.decision_history ?? [];
  const previousDecision = startup.human_resolution?.decision ?? null;
  const scoreSnapshot = startup.review
    ? {
        market_score: startup.review.market_score,
        product_score: startup.review.product_score,
        technical_score: startup.review.technical_score,
        execution_score: startup.review.execution_score,
        defensibility_score: startup.review.defensibility_score,
        overall_score: startup.review.overall_score ?? startup.review.aggregate_score,
        thesis_alignment_score: startup.review.thesis_alignment_score,
      }
    : null;
  const historyRecord = {
    company_id: startup.id,
    previous_decision: previousDecision,
    new_decision: decision,
    timestamp: now,
    rationale: notes,
    confidence: startup.partner?.confidence ?? null,
    score_snapshot: scoreSnapshot,
  };
  return {
    ...startup,
    human_resolution: {
      decision,
      notes,
      resolved_at: now,
    },
    conviction_state: {
      ...(startup.conviction_state ?? {}),
      current_ruling: {
        decision,
        rationale: notes,
        resolved_at: now,
        confidence: startup.partner?.confidence ?? null,
        score_snapshot: scoreSnapshot,
      },
      ruling_rationale: notes,
      decision_history: [...priorHistory, historyRecord],
    },
    partner: startup.partner
      ? {
          ...startup.partner,
          recommendation: decisionToPartnerRecommendation(decision),
          human_review_required: false,
        }
      : {
          recommendation: decisionToPartnerRecommendation(decision),
          human_review_required: false,
          decision_rationale: notes,
        },
  };
}

export function getBacklogPressure(startups: Startup[]) {
  const unresolved = startups.filter((s) => !isDealDecided(s));
  const adverse = unresolved.filter(hasMeaningfulAdverseItems);
  const oldest = unresolved
    .map((startup) => ({ startup, ageDays: getDealAgeDays(startup) ?? -1 }))
    .sort((a, b) => b.ageDays - a.ageDays)[0] ?? null;

  return {
    pendingCount: unresolved.length,
    adverseCount: adverse.length,
    oldest,
  };
}
