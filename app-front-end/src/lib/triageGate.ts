import type { Startup } from '../types/startup';

/** Mirrors backend/reviewer/engine.py's default confidence_threshold. This is
 * a display heuristic; the backend gate remains authoritative.
 *
 * confidence is no longer self-reported (product decision, 2026-08-19):
 * scout/engine.py now computes it as matched_categories/total_categories
 * against the mandate's structured fields (sector, stage, geography --
 * SCOUT_THESIS_FIT_CATEGORIES below), so it only ever lands on 0, 1/3, 2/3,
 * or 1. 0.5 is a deliberate midpoint threshold, not "50%" -- it sits
 * strictly between 1/3 and 2/3 so "at least 2 of 3 categories" passes
 * without relying on exact float equality against a repeating decimal. */
export const DEFAULT_REVIEW_CONFIDENCE_THRESHOLD = 0.5;
export const SCOUT_THESIS_FIT_CATEGORIES = 3;

export type TriageGateStatus =
  | { gated: false }
  | {
      gated: true;
      reason: 'not_reviewed';
      confidence: number;
      threshold: number;
    }

/**
 * Whether a startup's memo is being held back by the periodic pipeline's
 * triage funnel's Scout confidence gate. Partner decisions are intentionally
 * absent: their availability is determined by the canonical evidence
 * evaluation, never by a client-side reviewer-score calculation.
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
  return { gated: false };
}
