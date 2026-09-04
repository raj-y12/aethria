/**
 * Shared semantics for scores, verdicts, and decisions.
 * Align with versioned policy: resources/config/evaluation_rubric/v1.json (v1.1)
 * and resources/config/partner_rules/v1.json (via active.json).
 */

import type { Review, ScoreBand } from '../types/startup';

/**
 * Score band: human-readable meaning of a 1–10 score.
 *
 * These MUST mirror the canonical rubric `score_bands` in
 * `resources/config/evaluation_rubric/v1.json` (v1.1) — the same bands the
 * reviewer scores against. They were previously divergent (a `7` rendered as
 * "Strong" here while the rubric calls it "Promising"), which inverted the
 * verdict at the boundary where INVEST decisions are made (audit B1).
 *
 * NOTE: this is a hand-maintained mirror. P4.1 in the remediation plan replaces
 * it with bands derived from the policy payload so divergence becomes impossible.
 */
export const SCORE_BANDS = [
  { range: [1, 3] as [number, number], label: 'Weak', meaning: 'High risk, failing, or structurally broken.' },
  { range: [4, 5] as [number, number], label: 'Concerning', meaning: 'Unproven, material execution or validation gaps.' },
  { range: [6, 7] as [number, number], label: 'Promising', meaning: 'Reasonable thesis, requires validation.' },
  { range: [8, 10] as [number, number], label: 'Strong', meaning: 'Investment-grade, clear upside with managed risk.' },
] as const;

type ScoreBandCandidate = ScoreBand | (typeof SCORE_BANDS)[number];

export function getScoreBand(score: number, bands: readonly ScoreBandCandidate[] = SCORE_BANDS): { label: string; meaning: string } {
  if (!Number.isFinite(score) || score < 1 || score > 10) return { label: '—', meaning: '' };
  const band = bands.find((candidate) => {
    const [min, max] = 'range' in candidate ? candidate.range : [candidate.min, candidate.max];
    return score >= min && score <= max;
  });
  return band ? { label: band.label, meaning: band.meaning } : { label: '—', meaning: '' };
}

/**
 * Quality assessment from Reviewer (STRONG/MEDIUM/WEAK).
 *
 * These labels MUST stay word-disjoint from SCORE_BANDS (the dimension-band words
 * Weak/Concerning/Promising/Strong) so no single word means two different things on
 * the page (audit B2). MEDIUM was "Promising but incomplete" — "Promising" is also a
 * dimension band, so an analyst couldn't tell which axis "Promising" referred to.
 */
export const QUALITY_LABELS: Record<string, string> = {
  STRONG: 'Investment-grade',
  MEDIUM: 'Watchlist-grade',
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
