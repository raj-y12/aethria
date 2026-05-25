/**
 * Single place to resolve structured scoring from API review payloads.
 *
 * Resolution order:
 *   1. Full structured payload  (`review.scoring` / `structured_scoring` /
 *      `score_breakdown`, or a reviewer row carrying `structured_scoring`).
 *   2. Synthesised from flat per-dimension scores on the Review when the
 *      structured payload is missing (older / leaner backend responses).
 *
 * Returning `null` is reserved for "no scores at all" — both branches above
 * came up empty.
 */
import type { Review, ScoringDimension, StructuredScoring } from '../types/startup';

export function isScoringDimension(value: unknown): value is ScoringDimension {
  if (!value || typeof value !== 'object') return false;
  const casted = value as { score?: unknown; components?: unknown };
  return typeof casted.score === 'number' && !!casted.components && typeof casted.components === 'object';
}

const CONFIDENCE_TO_NUMBER: Record<string, number> = {
  low: 0.3,
  medium: 0.6,
  high: 0.9,
};

function flatConfidence(value: unknown): number | undefined {
  if (typeof value !== 'string') return undefined;
  const key = value.trim().toLowerCase();
  return CONFIDENCE_TO_NUMBER[key];
}

function cleanStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const entry of value) {
    if (typeof entry !== 'string') continue;
    const trimmed = entry.trim();
    if (!trimmed) continue;
    if (/^\[MISSING/i.test(trimmed)) continue;
    const key = trimmed.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(trimmed);
  }
  return out;
}

function nullableString(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

/** Build a `ScoringDimension`-shaped object from flat review fields. */
function flatDimension(
  score: unknown,
  confidence: unknown,
  reasoning: unknown,
  weaknesses: unknown,
  scoreLabel: unknown
): ScoringDimension | null {
  if (typeof score !== 'number' || !Number.isFinite(score)) return null;
  const reasoningList = cleanStringList(reasoning);
  const weaknessList = cleanStringList(weaknesses);
  return {
    score,
    confidence: flatConfidence(confidence) ?? null,
    components: {},
    reasoning: reasoningList.length > 0 ? reasoningList : null,
    weaknesses: weaknessList.length > 0 ? weaknessList : null,
    score_label: nullableString(scoreLabel),
  };
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

  // ── Path 1: full structured payload ──────────────────────────────────────
  if (candidate && typeof candidate.overall_score === 'number') {
    const { market, execution, product, technical, defensibility } = candidate;
    if (
      isScoringDimension(market) &&
      isScoringDimension(execution) &&
      isScoringDimension(product) &&
      isScoringDimension(technical) &&
      isScoringDimension(defensibility)
    ) {
      return {
        policy_version_id: candidate.policy_version_id,
        policy_hash: candidate.policy_hash,
        market,
        execution,
        product,
        technical,
        defensibility,
        overall_score: candidate.overall_score,
        overall_confidence: candidate.overall_confidence,
      };
    }
  }

  // ── Path 2: synthesise from flat per-dimension scores ────────────────────
  const market = flatDimension(
    review.market_score,
    review.market_confidence,
    review.market_reasoning,
    review.market_weaknesses,
    review.market_score_label
  );
  const product = flatDimension(
    review.product_score,
    review.product_confidence,
    review.product_reasoning,
    review.product_weaknesses,
    review.product_score_label
  );
  const technical = flatDimension(
    review.technical_score,
    review.technical_confidence,
    review.technical_reasoning,
    review.technical_weaknesses,
    review.technical_score_label
  );
  const execution = flatDimension(
    review.execution_score,
    review.execution_confidence,
    review.execution_reasoning,
    review.execution_weaknesses,
    review.execution_score_label
  );
  const defensibility = flatDimension(
    review.defensibility_score,
    review.defensibility_confidence,
    review.defensibility_reasoning,
    review.defensibility_weaknesses,
    review.defensibility_score_label
  );
  if (!market || !product || !technical || !execution || !defensibility) {
    return null;
  }
  const flatScores = [market.score, product.score, technical.score, execution.score, defensibility.score];
  const overallCandidate =
    typeof review.overall_score === 'number'
      ? review.overall_score
      : typeof review.aggregate_score === 'number'
        ? review.aggregate_score
        : flatScores.reduce((sum, s) => sum + s, 0) / flatScores.length;
  return {
    market,
    product,
    technical,
    execution,
    defensibility,
    overall_score: overallCandidate,
    overall_confidence: null,
  };
}

export function formatReviewOverallStructuredScore(review: Review | null | undefined): string {
  const normalized = normalizeStructuredScoring(review);
  if (normalized && typeof normalized.overall_score === 'number') {
    return normalized.overall_score.toFixed(1);
  }
  return '—';
}

const INTERNAL_REASONING_PATTERNS = [
  /^Computed from\b/i,
  /\bfrom scout payload\b/i,
  /\bfrom scout narrative\b/i,
  /\bfrom reviewer\b/i,
  /\bGrowth inferred from\b/i,
  /\bTAM from scout\b/i,
  /\bextracted? from\b/i,
  /\bpolicy[_\s]?hash\b/i,
  /\bpolicy[_\s]?version\b/i,
  /\bsource_components?\b/i,
  /\bnormalize_/i,
  /\b_extract_/i,
  /\bclassify_/i,
  /\braw extraction\b/i,
  /\bMissing-data rule:/i,
  /\bsignal pipeline\b/i,
  /\bscoring_engine\b/i,
  /\baggregation_layer\b/i,
  /\bnormalization_layer\b/i,
  /\bextraction_layer\b/i,
  /\bpolicy_compiler\b/i,
  /\bWeight \d+%/i,
  /\bEvidence partial\b/i,
  /\bEvidence: missing\b/i,
  /\bEvidence: complete\b/i,
  /\bStructured scoring\b/i,
  /\bNormalization\b/i,
  /\bAggregation\b/i,
  /\bRule engine\b/i,
  /\bPolicy inputs\b/i,
  /\bComponent weights\b/i,
];

/**
 * Strip internal/debug reasoning from user-facing text.
 * Returns cleaned string or null if the entire string is internal.
 */
export function sanitizeReasoning(text: string | null | undefined): string | null {
  if (!text || typeof text !== 'string') return null;
  const trimmed = text.trim();
  if (!trimmed) return null;

  for (const pattern of INTERNAL_REASONING_PATTERNS) {
    if (pattern.test(trimmed)) {
      const sentences = trimmed.split(/(?<=[.!?])\s+/);
      const clean = sentences.filter((s) => {
        const st = s.trim();
        return st.length > 0 && !INTERNAL_REASONING_PATTERNS.some((p) => p.test(st));
      });
      return clean.length > 0 ? clean.join(' ') : null;
    }
  }
  return trimmed;
}

/**
 * Check whether a component has concrete evidence vs missing/neutral.
 * Returns 'complete', 'partial', or 'missing'.
 */
export function assessEvidenceStatus(component: {
  value?: string | null;
  label?: string | null;
  evidence?: string | null;
  score?: number;
  confidence?: number | null;
}): 'complete' | 'partial' | 'missing' {
  const value = String(component.value ?? '').trim();
  const label = String(component.label ?? '').trim();
  const evidence = String(component.evidence ?? '').trim();
  const hasConcrete = (value.length > 0 && !/^\[?\s*missing/i.test(value))
    || (label.length > 0 && !/^\[?\s*missing/i.test(label));
  if (!hasConcrete) return 'missing';
  if (!evidence && (component.confidence == null || component.confidence < 0.4)) return 'partial';
  return 'complete';
}
