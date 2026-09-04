import type { LookupResultSnapshotProps } from '@aethria/product-chrome';
import type { EvaluationRecord } from '../api/evaluations';
import type { Startup } from '../types/startup';
import { canonicalCriteriaToStructuredScoring } from './canonicalScoring';
import { badgeTextColorForBackground, DEFAULT_VERDICT_BADGES, type VerdictBadgeConfig } from './fundConfiguration';

const DIMENSION_KEYS = ['market', 'execution', 'product', 'technical', 'defensibility'] as const;
const DIMENSION_LABELS: Record<(typeof DIMENSION_KEYS)[number], string> = {
  market: 'MKT',
  execution: 'EXEC',
  product: 'PROD',
  technical: 'TECH',
  defensibility: 'DEF',
};

const RESOLUTION_STATUS_LABELS: Record<string, string> = {
  FOUND: 'Identity confirmed',
  PARTIAL: 'Partial evidence',
  LOW_CONFIDENCE: 'Low-confidence match',
  NEEDS_REVIEW: 'Needs review',
  NOT_FOUND: 'Not found',
};

const RESOLUTION_MISSING_LABELS: Record<string, string> = {
  website: 'website',
  linkedin_url: 'LinkedIn',
  funding_profile: 'funding profile',
  founder_names: 'founders',
  description: 'description',
  news_mentions: 'news mentions',
};

/** Company Resolver transparency line — only shown when identity isn't fully confirmed,
 * so a weak lookup explains itself instead of looking like a random failure. */
export function buildResolutionLine(startup: Startup): string | undefined {
  const status = (startup.scout.resolution_status ?? '').toString().toUpperCase();
  if (!status || status === 'FOUND') return undefined;
  const label = RESOLUTION_STATUS_LABELS[status] ?? status;
  const resolution = startup.scout.company_resolution;
  const missing = (resolution?.missing_fields ?? [])
    .map((f) => RESOLUTION_MISSING_LABELS[f] ?? f)
    .slice(0, 4);
  const evidenceCount = resolution?.evidence_sources?.length ?? 0;
  const bits = [label];
  if (evidenceCount > 0) bits.push(`${evidenceCount} source${evidenceCount === 1 ? '' : 's'}`);
  if (missing.length > 0) bits.push(`missing ${missing.join(', ')}`);
  return bits.join(' · ');
}

export function buildLookupSnapshotProps(
  startup: Startup,
  queryLabel?: string,
  verdictBadges?: VerdictBadgeConfig[],
  evaluation?: EvaluationRecord | null,
): LookupResultSnapshotProps | null {
  const review = startup.review;
  if (!review) return null;

  // Canonical evidence evaluation is the sole score source. A lookup result
  // without it stays pending rather than presenting reviewer numerics.
  const canonicalScoring = canonicalCriteriaToStructuredScoring(evaluation);
  const scoring = canonicalScoring;
  if (!scoring) return null;

  // Lead with the partner recommendation (INVEST / MONITOR / PASS) — the decision,
  // not the reviewer quality band (STRONG/MEDIUM/WEAK). Fall back to band, then status.
  const recommendation = startup.partner?.recommendation;
  const verdict = recommendation ? `${recommendation}.` : 'REVIEWING.';

  // Filled chip, matching DecisionBadge: configured colour is the fill,
  // with a computed contrasting ink for readability.
  const badges = verdictBadges ?? DEFAULT_VERDICT_BADGES;
  const verdictColor = recommendation
    ? badges.find((b) => b.id === recommendation)?.backgroundColor ?? null
    : null;
  const verdictTextColor = verdictColor ? badgeTextColorForBackground(verdictColor) : null;
  const sector = startup.scout.sector?.trim();
  const stage = startup.scout.funding_stage?.trim();
  const metaParts = [sector, stage].filter(Boolean);

  const thesisBits: string[] = [];
  if (review.thesis_matches_fund === true) thesisBits.push('Thesis-aligned');
  if (review.thesis_matches_fund === false) thesisBits.push('Thesis deviation');
  if (typeof review.thesis_alignment_score === 'number') {
    thesisBits.push(`${Math.round(review.thesis_alignment_score * 100)}% alignment`);
  }

  // The standfirst is the review's own synthesis — thesis fit already has its
  // dedicated mono line below, so thesis_fit_line here would say it twice.
  const summary =
    review.overall_summary?.trim() ||
    startup.scout.one_line?.trim() ||
    'Analyst review in progress.';

  const dimensions = DIMENSION_KEYS.map((key) => {
    const dim = scoring?.[key];
    // Canonical's unscored dimensions carry score: 0 (a real number, not
    // null) as a sentinel -- checking typeof alone would render "0" instead
    // of the memo's "Not scored", so unscored must be checked explicitly.
    const score =
      typeof dim?.score === 'number' && !dim.unscored
        ? dim.score
        : null;
    return {
      key,
      label: DIMENSION_LABELS[key],
      score,
    };
  });

  return {
    companyName: startup.scout.name,
    queryLabel: queryLabel?.trim() || startup.scout.lookup_query?.trim() || undefined,
    metaLine: metaParts.length > 0 ? metaParts.join(' · ') : undefined,
    verdict,
    verdictColor,
    verdictTextColor,
    summary,
    dimensions,
    thesisLine: thesisBits.length > 0 ? thesisBits.join(' · ') : undefined,
    resolutionLine: buildResolutionLine(startup),
    // Fuller, enlarged layout for the dispatch result takeover: bigger company name,
    // summary and dimension scores (same tags/styling), never the tight rail strip.
    compact: false,
    size: 'lg',
  };
}
