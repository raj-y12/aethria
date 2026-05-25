/**
 * Shared semantics for scores, verdicts, and decisions.
 * Align with versioned policy: resources/config/evaluation_rubric/v1.json (v1.1)
 * and resources/config/partner_rules/v1.json (via active.json).
 */

import type { Review } from '../types/startup';

/** Score band: human-readable meaning of a 1–10 score. Aligned with canonical bands. */
export const SCORE_BANDS = [
  { range: [1, 2] as [number, number], label: 'Structurally Weak', meaning: 'Fundamental structural concerns. Not investable without significant change.' },
  { range: [3, 4] as [number, number], label: 'Below Threshold', meaning: 'Potential business but unlikely venture-scale outcome at current state.' },
  { range: [5, 6] as [number, number], label: 'Promising', meaning: 'Promising opportunity with incomplete validation. Requires further diligence.' },
  { range: [7, 8] as [number, number], label: 'Strong', meaning: 'Strong venture-scale opportunity supported by evidence.' },
  { range: [9, 10] as [number, number], label: 'Exceptional', meaning: 'Exceptional opportunity with multiple reinforcing signals.' },
] as const;

export function getScoreBand(score: number): { label: string; meaning: string } {
  if (!Number.isFinite(score) || score < 1 || score > 10) return { label: '—', meaning: '' };
  if (score < 3) return { label: SCORE_BANDS[0].label, meaning: SCORE_BANDS[0].meaning };
  if (score < 5) return { label: SCORE_BANDS[1].label, meaning: SCORE_BANDS[1].meaning };
  if (score < 7) return { label: SCORE_BANDS[2].label, meaning: SCORE_BANDS[2].meaning };
  if (score < 9) return { label: SCORE_BANDS[3].label, meaning: SCORE_BANDS[3].meaning };
  return { label: SCORE_BANDS[4].label, meaning: SCORE_BANDS[4].meaning };
}

/** Quality assessment from Reviewer (STRONG/MEDIUM/WEAK). */
export const QUALITY_LABELS: Record<string, string> = {
  STRONG: 'Investment-grade',
  MEDIUM: 'Promising but incomplete',
  WEAK: 'Early and unproven',
};

export type ReviewerQualityBand = 'STRONG' | 'MEDIUM' | 'WEAK';

/** Consensus / primary reviewer verdict band (same resolution as WorkGrid filters). */
export function getReviewerQualityBand(review: Review | null | undefined): ReviewerQualityBand | null {
  if (!review) return null;
  const c = review.consensus_verdict;
  if (c === 'STRONG' || c === 'MEDIUM' || c === 'WEAK') return c;
  const d = review.derived_verdict;
  if (d === 'STRONG' || d === 'MEDIUM' || d === 'WEAK') return d;
  const v = typeof review.verdict === 'string' ? review.verdict.trim().toUpperCase() : '';
  if (v === 'STRONG' || v === 'MEDIUM' || v === 'WEAK') return v as ReviewerQualityBand;
  const first = review.reviews?.[0]?.verdict;
  if (first === 'STRONG' || first === 'MEDIUM' || first === 'WEAK') return first;
  return null;
}

/** Investment decision from Partner (INVEST/PASS/MONITOR). */
export const DECISION_LABELS: Record<string, string> = {
  INVEST: 'Invest',
  PASS: 'Pass',
  MONITOR: 'Monitor',
};

/** Dimension display order: primary drivers first, then supporting. */
export const SCORE_DIMENSIONS = [
  { id: 'market_score', name: 'Market' },
  { id: 'execution_score', name: 'Execution' },
  { id: 'product_score', name: 'Product' },
  { id: 'technical_score', name: 'Technical' },
  { id: 'defensibility_score', name: 'Defensibility' },
] as const;
