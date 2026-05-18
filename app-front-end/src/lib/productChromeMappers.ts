import type { FundThesisSummary } from '../api/fundThesis';
import type { Settings } from '../api/settings';
import type { LookupResultSnapshotProps, MandateCardProps } from '@aethria/product-chrome';
import { getReviewerQualityBand } from '../design-system/semantics';
import type { Startup } from '../types/startup';
import { normalizeStructuredScoring } from './reviewScoring';

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

export function buildLookupSnapshotProps(
  startup: Startup,
  queryLabel?: string,
): LookupResultSnapshotProps | null {
  const review = startup.review;
  if (!review) return null;

  const scoring = normalizeStructuredScoring(review);
  const band = getReviewerQualityBand(review);
  if (!band && !scoring) return null;

  const verdict = band ? `${band}.` : 'REVIEWING.';
  const sector = startup.scout.sector?.trim();
  const stage = startup.scout.funding_stage?.trim();
  const metaParts = [sector, stage].filter(Boolean);

  const thesisBits: string[] = [];
  if (review.thesis_matches_fund === true) thesisBits.push('Thesis-aligned');
  if (review.thesis_matches_fund === false) thesisBits.push('Thesis deviation');
  if (typeof review.thesis_alignment_score === 'number') {
    thesisBits.push(`${Math.round(review.thesis_alignment_score * 100)}% alignment`);
  }

  const summary =
    review.aethria_view?.thesis_fit_line?.trim() ||
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
    summary,
    dimensions,
    thesisLine: thesisBits.length > 0 ? thesisBits.join(' · ') : undefined,
    compact: true,
  };
}
