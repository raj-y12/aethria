import type { FundThesisSummary } from '../api/fundThesis';
import type { Settings } from '../api/settings';
import type { LookupResultSnapshotProps, MandateCardProps } from '@aethria/product-chrome';
import { getReviewerQualityBand } from '../design-system/semantics';
import type { Startup } from '../types/startup';
import { normalizeStructuredScoring } from './reviewScoring';
import {
  DEFAULT_VERDICT_BADGES,
  badgeTextColorForBackground,
  type VerdictBadgeConfig,
} from './fundConfiguration';

const DIMENSION_KEYS = ['market', 'execution', 'product', 'technical', 'defensibility'] as const;
const DIMENSION_LABELS: Record<(typeof DIMENSION_KEYS)[number], string> = {
  market: 'MKT',
  execution: 'EXEC',
  product: 'PROD',
  technical: 'TECH',
  defensibility: 'DEF',
};

function thesisFundName(
  fundThesisSummary: FundThesisSummary | null,
  settings: Settings | null | undefined,
): string {
  const pj = fundThesisSummary?.parsed_json;
  if (pj && typeof pj === 'object') {
    for (const key of ['fund_name', 'name', 'title', 'fund', 'fund_title']) {
      const val = (pj as Record<string, unknown>)[key];
      if (typeof val === 'string' && val.trim()) return val.trim();
    }
  }
  const settingsName = settings?.fund_identity?.fund_name?.trim();
  if (settingsName) return settingsName;
  if (fundThesisSummary?.active_version_number != null) {
    return `Fund Thesis v${fundThesisSummary.active_version_number}`;
  }
  return '';
}

function thesisTags(
  fundThesisSummary: FundThesisSummary | null,
  settings: Settings | null | undefined,
): string[] {
  const fundStage = settings?.fund_identity?.stage_focus?.trim() || '';
  const fundGeo = settings?.fund_identity?.geographic_focus?.trim() || '';
  const scoutRegionRaw = settings?.agent_config?.scout_region?.trim() || '';
  const scoutRegion =
    scoutRegionRaw.length > 0
      ? scoutRegionRaw.charAt(0).toUpperCase() + scoutRegionRaw.slice(1).toLowerCase()
      : '';

  const pj = fundThesisSummary?.parsed_json as Record<string, unknown> | undefined;
  const toStrings = (v: unknown): string[] => {
    if (Array.isArray(v)) return v.filter((x): x is string => typeof x === 'string' && !!x.trim()).map((x) => x.trim());
    if (typeof v === 'string' && v.trim()) return [v.trim()];
    return [];
  };
  const sectors = pj ? toStrings(pj.sectors ?? pj.sector ?? pj.focus_areas) : [];
  const stages = pj ? toStrings(pj.stage_focus ?? pj.stage) : fundStage ? [fundStage] : [];
  const geos = pj
    ? toStrings(pj.geography ?? pj.geographies ?? pj.geographic_focus)
    : fundGeo
      ? [fundGeo]
      : scoutRegion
        ? [scoutRegion]
        : [];
  return [...stages, ...geos, ...sectors];
}

function thesisExcerpt(fundThesisSummary: FundThesisSummary | null): string | undefined {
  const raw = fundThesisSummary?.raw_text?.trim();
  if (!raw) return undefined;
  const firstParagraph = raw.split(/\n\n+/)[0]?.trim();
  if (!firstParagraph) return undefined;
  return firstParagraph.length > 220 ? `${firstParagraph.slice(0, 217)}…` : firstParagraph;
}

export function buildMandateCardProps(
  fundThesisSummary: FundThesisSummary | null,
  settings: Settings | null | undefined,
): MandateCardProps | null {
  const title = thesisFundName(fundThesisSummary, settings);
  if (!title && !fundThesisSummary?.active_version_id) return null;
  const tags = thesisTags(fundThesisSummary, settings);
  return {
    variant: 'paper',
    title: title || 'Fund mandate',
    tags: tags.length > 0 ? tags : undefined,
    excerpt: thesisExcerpt(fundThesisSummary),
    live: Boolean(fundThesisSummary?.active_version_id),
    compact: true,
  };
}

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
): LookupResultSnapshotProps | null {
  const review = startup.review;
  if (!review) return null;

  const scoring = normalizeStructuredScoring(review);
  const band = getReviewerQualityBand(review);
  if (!band && !scoring) return null;

  // Lead with the partner recommendation (INVEST / MONITOR / PASS) — the decision,
  // not the reviewer quality band (STRONG/MEDIUM/WEAK). Fall back to band, then status.
  const recommendation = startup.partner?.recommendation;
  const verdict = recommendation ? `${recommendation}.` : band ? `${band}.` : 'REVIEWING.';

  // Match the queue: a filled badge in the configured (soft-palette) colour.
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

  const flatScores: Record<(typeof DIMENSION_KEYS)[number], number | undefined> = {
    market: review.market_score,
    execution: review.execution_score,
    product: review.product_score,
    technical: review.technical_score,
    defensibility: review.defensibility_score,
  };

  const dimensions = DIMENSION_KEYS.map((key) => {
    const dim = scoring?.[key];
    const score =
      typeof dim?.score === 'number'
        ? dim.score
        : typeof flatScores[key] === 'number'
          ? flatScores[key]!
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
