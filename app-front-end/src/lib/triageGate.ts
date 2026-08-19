import type { Startup } from '../types/startup';

/** Mirrors backend/reviewer/engine.py's default confidence_threshold and
 * backend/partner/engine.py's default decision_threshold (utils/scoring.py's
 * compute_overall_score). Per-tenant overrides live server-side only; this
 * is a display heuristic, not the enforcement point -- the backend gate is
 * authoritative and re-checked on every manual-override call.
 *
 * confidence is no longer self-reported (product decision, 2026-08-19):
 * scout/engine.py now computes it as matched_categories/total_categories
 * against the mandate's structured fields (sector, stage, geography --
 * SCOUT_THESIS_FIT_CATEGORIES below), so it only ever lands on 0, 1/3, 2/3,
 * or 1. 0.5 is a deliberate midpoint threshold, not "50%" -- it sits
 * strictly between 1/3 and 2/3 so "at least 2 of 3 categories" passes
 * without relying on exact float equality against a repeating decimal. */
export const DEFAULT_REVIEW_CONFIDENCE_THRESHOLD = 0.5;
export const DEFAULT_DECISION_SCORE_THRESHOLD = 0.55;
export const SCOUT_THESIS_FIT_CATEGORIES = 3;

export type TriageGateStatus =
  | { gated: false }
  | {
      gated: true;
      reason: 'not_reviewed';
      confidence: number;
      threshold: number;
    }
  | {
      gated: true;
      reason: 'not_decided';
      overallScore: number;
      threshold: number;
    };

function computeOverallScore(review: NonNullable<Startup['review']>): number | null {
  const fields = [review.market_score, review.product_score, review.technical_score, review.execution_score];
  if (fields.some((v) => typeof v !== 'number' || Number.isNaN(v))) return null;
  return (fields as number[]).reduce((a, b) => a + b, 0) / fields.length;
}

/**
 * Whether a startup's memo is being held back by the periodic pipeline's
 * triage funnel gates, and why. A startup with `review == null` was never
 * reviewed (scout confidence below threshold). A startup with `review` but
 * no `partner` AND a computable overall score below the decision threshold
 * was reviewed but never decided.
 *
 * A missing/unparseable overall score is deliberately NOT treated as gated
 * here (unlike the backend, which fails closed): an on-demand lookup memo
 * can legitimately have `review` set while its own decision is still being
 * generated, and there's no reliable client-side signal to tell that apart
 * from a periodic-pipeline gate. This heuristic only fires on the
 * unambiguous case; the backend override endpoint remains the real gate.
 */
export function getTriageGateStatus(startup: Startup): TriageGateStatus {
  if (!startup.review) {
    const confidence = startup.scout.confidence;
    // A startup can be unreviewed simply because its cycle hasn't come up
    // yet (Reviewer processes a bounded batch per cycle) -- that is not the
    // same as being held by the confidence gate. Only report "held by
    // triage funnel" when confidence is actually below the bar; otherwise
    // this isn't gated, it's just pending, and the memo's normal
    // generating/empty state should show instead.
    if (confidence < DEFAULT_REVIEW_CONFIDENCE_THRESHOLD) {
      return {
        gated: true,
        reason: 'not_reviewed',
        confidence,
        threshold: DEFAULT_REVIEW_CONFIDENCE_THRESHOLD,
      };
    }
    return { gated: false };
  }
  if (!startup.partner) {
    const overallScore = computeOverallScore(startup.review);
    if (overallScore != null && overallScore / 10 < DEFAULT_DECISION_SCORE_THRESHOLD) {
      return {
        gated: true,
        reason: 'not_decided',
        overallScore,
        threshold: DEFAULT_DECISION_SCORE_THRESHOLD,
      };
    }
  }
  return { gated: false };
}
