/**
 * Single place to resolve structured scoring from API review payloads.
 * Backend mirrors structured_scoring / scoring / score_breakdown; this helper
 * still checks nested reviewer rows for older rows.
 */
import type { Review, ScoringDimension, StructuredScoring } from '../types/startup';

export function isScoringDimension(value: unknown): value is ScoringDimension {
  if (!value || typeof value !== 'object') return false;
  const casted = value as { score?: unknown; components?: unknown };
  return typeof casted.score === 'number' && !!casted.components && typeof casted.components === 'object';
}

export function normalizeStructuredScoring(review: Review | null | undefined): StructuredScoring | null {
  if (!review) return null;
  const reviewRecord = review as Record<string, unknown>;
  const reviewerStructuredCandidate = Array.isArray(reviewRecord.reviews)
    ? (reviewRecord.reviews as Array<Record<string, unknown>>).find(
        (entry) => !!entry && typeof entry === 'object' && !!entry.structured_scoring
      )?.structured_scoring
    : null;
  const candidate =
    (reviewRecord.scoring as StructuredScoring | undefined) ??
    (reviewRecord.structured_scoring as StructuredScoring | undefined) ??
    (reviewRecord.score_breakdown as StructuredScoring | undefined) ??
    (reviewerStructuredCandidate as StructuredScoring | undefined);

  const source = candidate ?? (review as unknown as Record<string, unknown>);
  if (typeof source.overall_score !== 'number') return null;
  const market = source.market;
  const execution = source.execution;
  const product = source.product;
  const technical = source.technical;
  const defensibility = source.defensibility;
  if (
    !isScoringDimension(market) ||
    !isScoringDimension(execution) ||
    !isScoringDimension(product) ||
    !isScoringDimension(technical) ||
    !isScoringDimension(defensibility)
  ) {
    return null;
  }
  return {
    market,
    execution,
    product,
    technical,
    defensibility,
    overall_score: source.overall_score,
  };
}

export function formatReviewOverallStructuredScore(review: Review | null | undefined): string {
  const normalized = normalizeStructuredScoring(review);
  if (normalized && typeof normalized.overall_score === 'number') {
    return normalized.overall_score.toFixed(1);
  }
  return '—';
}
