import type { Settings } from '../api/settings';
import type { Startup } from '../types/startup';

export type CoreDimensionKey =
  | 'market'
  | 'product'
  | 'technical'
  | 'execution'
  | 'defensibility';

export type ScoringDimensionKey =
  | CoreDimensionKey
  | 'traction'
  | 'timing'
  | 'fundFit';

export const CANONICAL_DIMENSION_KEYS: readonly CoreDimensionKey[] = [
  'market', 'product', 'technical', 'execution', 'defensibility',
] as const;

export interface CanonicalDimension {
  key: CoreDimensionKey;
  label: string;
  description: string;
}

export const CANONICAL_DIMENSIONS: Record<CoreDimensionKey, CanonicalDimension> = {
  market: {
    key: 'market',
    label: 'Market',
    description: 'Market size, growth trajectory, competitive density, and urgency of the problem being solved.',
  },
  product: {
    key: 'product',
    label: 'Product',
    description: 'Strength of the value proposition, user pull, workflow fit, differentiation, and retention potential.',
  },
  technical: {
    key: 'technical',
    label: 'Technical',
    description: 'Technical depth, architecture maturity, engineering quality, scalability ceiling, and data advantage.',
  },
  execution: {
    key: 'execution',
    label: 'Execution',
    description: 'Traction evidence, growth velocity, go-to-market effectiveness, team caliber, and operational speed.',
  },
  defensibility: {
    key: 'defensibility',
    label: 'Defensibility',
    description: 'Network effects, switching costs, proprietary data position, barriers to entry, and brand strength.',
  },
};

export interface DimensionScoreBand {
  score: number;
  description: string;
}

export const DIMENSION_SCORE_BANDS: Record<CoreDimensionKey, Record<number, string>> = {
  market: {
    1: 'No identifiable market. Problem is not validated or budget does not exist.',
    2: 'Extremely niche market with no growth trajectory. Insufficient for venture returns.',
    3: 'Small addressable market or declining category. Growth rate below replacement.',
    4: 'Addressable market exists but TAM under $1B or growth is flat. Competitive density is high.',
    5: 'Market is real and growing but TAM validation is incomplete. Budget exists but urgency is unclear.',
    6: 'Growing market with validated demand. TAM appears sufficient but independent verification is missing.',
    7: 'Large, expanding market with clear buyer urgency. Multiple data points support TAM above $3B.',
    8: 'Strong market with verified TAM, healthy growth rate, and clear category tailwinds.',
    9: 'Exceptional market with verified TAM above $10B, strong growth, and urgent buyer need.',
    10: 'Generational market opportunity. Category-defining tailwinds with massive, verified TAM.',
  },
  product: {
    1: 'No product insight. Solution does not address a real workflow or need.',
    2: 'Product exists but has no differentiation and no evidence of user pull.',
    3: 'Product addresses a real problem but value proposition is unclear. No retention evidence.',
    4: 'Functional product with some user interest but weak differentiation from alternatives.',
    5: 'Product solves a real problem with some user pull. Differentiation is emerging but unproven.',
    6: 'Clear value proposition with early user traction. Differentiation is present but competitive moat is thin.',
    7: 'Strong product-market signal with demonstrated user pull and clear differentiation.',
    8: 'Compelling product with strong retention signals and defensible differentiation.',
    9: 'Exceptional product insight with deep user love, high retention, and unique workflow integration.',
    10: 'Category-defining product. Users cannot imagine returning to the previous solution.',
  },
  technical: {
    1: 'No technical depth. Implementation is trivial and easily replicated.',
    2: 'Minimal technical complexity. No architecture advantage or engineering differentiation.',
    3: 'Basic implementation with limited scalability. Technical debt is likely high.',
    4: 'Functional but unremarkable technical approach. Scalability concerns exist.',
    5: 'Competent engineering with some technical depth. Scalability path is plausible but unproven.',
    6: 'Solid technical foundation with clear scalability path. Some engineering differentiation.',
    7: 'Strong technical implementation with proven scalability and meaningful engineering edge.',
    8: 'Excellent engineering quality with defensible technical architecture and data advantage.',
    9: 'Deep technical moat with proprietary systems, strong data advantage, and elite engineering.',
    10: 'World-class technical achievement. Architecture creates compounding advantage over time.',
  },
  execution: {
    1: 'No evidence of execution capability. Team background is unknown or misaligned.',
    2: 'Team exists but has no relevant domain experience and no traction evidence.',
    3: 'Some team credibility but no meaningful traction. Execution speed is unclear.',
    4: 'Team has relevant background but traction is minimal. Go-to-market is untested.',
    5: 'Credible team with early traction signals. Execution velocity is moderate.',
    6: 'Strong team with demonstrated early traction. Go-to-market channels are identified.',
    7: 'Proven execution with meaningful traction metrics and strong operational velocity.',
    8: 'Exceptional execution with rapid growth, proven GTM, and high-caliber team.',
    9: 'Elite team with exceptional traction trajectory and repeatable go-to-market engine.',
    10: 'World-class founders with breakthrough traction. Execution is a compounding advantage.',
  },
  defensibility: {
    1: 'No defensibility. Any competitor could replicate the offering immediately.',
    2: 'Minimal barriers to entry. No switching costs, network effects, or data advantage.',
    3: 'Some barriers exist but they are easily overcome. Switching costs are low.',
    4: 'Emerging defensibility through early data or distribution but moat is thin.',
    5: 'Moderate defensibility with some switching costs or early network effects.',
    6: 'Clear defensibility path with meaningful switching costs or growing data advantage.',
    7: 'Strong moat with multiple defensibility layers. Switching costs are significant.',
    8: 'Deep moat with strong network effects, high switching costs, and proprietary data.',
    9: 'Exceptional defensibility with compounding network effects and deep platform lock-in.',
    10: 'Near-impregnable competitive position. Multiple reinforcing moats create winner-take-most dynamics.',
  },
};

export const UNIVERSAL_SCORE_BANDS: Array<{
  range: [number, number];
  label: string;
  description: string;
}> = [
  { range: [1, 2], label: 'Structurally Weak', description: 'Fundamental weaknesses that are unlikely to be overcome. Not a viable venture opportunity.' },
  { range: [3, 4], label: 'Below Threshold', description: 'Potential business but unlikely to produce venture-scale outcomes. Significant gaps remain.' },
  { range: [5, 6], label: 'Promising, Incomplete', description: 'Promising opportunity with incomplete validation. Further diligence could materially change the assessment.' },
  { range: [7, 8], label: 'Strong', description: 'Strong venture-scale opportunity supported by evidence. Key signals are present and validated.' },
  { range: [9, 10], label: 'Exceptional', description: 'Exceptional opportunity with multiple reinforcing signals. Rare conviction level.' },
];

export function getDimensionScoreBand(dimension: CoreDimensionKey, score: number): string {
  const bands = DIMENSION_SCORE_BANDS[dimension];
  const rounded = Math.max(1, Math.min(10, Math.round(score)));
  return bands[rounded] ?? '';
}

export function getConfidenceInterpretation(confidence: number): {
  level: 'high' | 'medium' | 'low';
  interpretation: string;
} {
  if (confidence >= 0.7) {
    return {
      level: 'high',
      interpretation: 'Evidence is sufficient to support the assigned score with reasonable certainty.',
    };
  }
  if (confidence >= 0.45) {
    return {
      level: 'medium',
      interpretation: 'Evidence supports the general direction but key data points are missing. Score could shift materially with additional diligence.',
    };
  }
  return {
    level: 'low',
    interpretation: 'Evidence is insufficient to support a strong conclusion. Additional diligence could materially change the outcome in either direction.',
  };
}

export type DecisionLabel = 'Pass' | 'Monitor' | 'Invest';
export type RiskSensitivity = 'conservative' | 'balanced' | 'aggressive';
export type MemoStyle = 'concise' | 'standard' | 'detailed';
export type MemoTone = 'partner' | 'analyst';
export type VerdictBadgeId = 'INVEST' | 'MONITOR' | 'PASS' | 'STRONG' | 'MEDIUM' | 'WEAK';

export interface FundMandateConfig {
  fundName: string;
  mandateName: string;
  preferredStages: string[];
  preferredSectors?: string[];
  excludedSectorList?: string[];
  geographyPreferences?: string[];
  geographies: string[];
  customGeography: string;
  sectors: string[];
  customSectors: string;
  excludedSectors: string;
  businessModels: string;
  checkSizeMin: number;
  checkSizeMax: number;
  ownershipTarget: number;
  minimumTraction: string;
  thesisText: string;
}

export interface ScoringWeight {
  key: ScoringDimensionKey;
  label: string;
  description: string;
  weight: number;
}

export interface ScoreBand {
  id: string;
  min: number;
  max: number;
  label: DecisionLabel;
  tone: 'negative' | 'watch' | 'review' | 'positive' | 'strong';
}

export interface VerdictBadgeConfig {
  id: VerdictBadgeId;
  label: string;
  backgroundColor: string;
}

export interface DecisionThresholdConfig {
  autoPass: number;
  monitor: number;
  escalation: number;
  partnerReview: number;
  staleAfterHours: number;
  confidenceFloor: number;
  missingDataThreshold: number;
}

export interface RiskConfig {
  sensitivity: RiskSensitivity;
  requireAcknowledgement: boolean;
  onlyGateHighSeverity: boolean;
  missingFounderPenalty: number;
  missingTractionPenalty: number;
  contradictionPenalty: number;
  weakSourcePenalty: number;
}

export interface MemoConfig {
  style: MemoStyle;
  deepDiveCollapsed: boolean;
  includeEvidenceExcerpts: boolean;
  includeMissingData: boolean;
  includeScoreReasoning: boolean;
  includeSourceConfidence: boolean;
  tone: MemoTone;
}

export interface RubricCriterion {
  id: string;
  dimension: ScoringDimensionKey;
  name: string;
  description: string;
  weight: number;
  positiveSignals: string;
  negativeSignals: string;
  missingDataBehavior: string;
  examples: {
    score3: string;
    score5: string;
    score7: string;
    score9: string;
  };
}

export interface FundConfiguration {
  versionLabel: string;
  version: number;
  lastSavedAt: string | null;
  activePolicyVersionId?: string | null;
  draftPolicyHash?: string | null;
  publishedPolicyHash?: string | null;
  lastPublishedAt?: string | null;
  mandate: FundMandateConfig;
  scoringWeights: ScoringWeight[];
  scoreBands: ScoreBand[];
  verdictBadges: VerdictBadgeConfig[];
  thresholds: DecisionThresholdConfig;
  risk: RiskConfig;
  memo: MemoConfig;
  rubric: RubricCriterion[];
}

export interface WeightValidation {
  total: number;
  valid: boolean;
  delta: number;
}

export interface BandValidation {
  valid: boolean;
  errors: string[];
}

export const FUND_CONFIG_STORAGE_KEY = 'aethria_fund_configuration_v1';
export const FUND_CONFIG_EVENT = 'aethria-fund-configuration-updated';

export function thesisVersionLabel(versionNumber?: number | null): string {
  if (versionNumber == null || versionNumber < 1) return 'Fund Thesis';
  return `Fund Thesis v${versionNumber}`;
}

export function applyThesisVersionMetadata(
  config: FundConfiguration,
  versionNumber?: number | null,
): FundConfiguration {
  const version = versionNumber != null && versionNumber >= 1 ? versionNumber : config.version;
  return {
    ...config,
    version,
    versionLabel: thesisVersionLabel(version),
  };
}
const KNOWN_SECTOR_OPTIONS = new Set(['B2B SaaS', 'AI', 'Infrastructure', 'Fintech', 'Healthcare', 'Devtools', 'Climate']);
const KNOWN_GEOGRAPHY_OPTIONS = new Set(['US', 'Europe', 'UK', 'India', 'Global']);

export const dimensionDescriptions: Record<ScoringDimensionKey, string> = {
  market: CANONICAL_DIMENSIONS.market.description,
  product: CANONICAL_DIMENSIONS.product.description,
  technical: CANONICAL_DIMENSIONS.technical.description,
  execution: CANONICAL_DIMENSIONS.execution.description,
  defensibility: CANONICAL_DIMENSIONS.defensibility.description,
  traction: 'Usage, revenue, retention, references, and repeatability.',
  timing: 'Why this company can win now rather than later.',
  fundFit: 'Alignment with mandate, ownership model, geography, and portfolio construction.',
};

export const DEFAULT_SCORING_WEIGHTS: ScoringWeight[] = CANONICAL_DIMENSION_KEYS.map((key) => ({
  key,
  label: CANONICAL_DIMENSIONS[key].label,
  description: CANONICAL_DIMENSIONS[key].description,
  weight: 20,
}));

export const DEFAULT_SCORE_BANDS: ScoreBand[] = [
  { id: 'pass', min: 0, max: 59, label: 'Pass', tone: 'negative' },
  { id: 'monitor', min: 60, max: 79, label: 'Monitor', tone: 'watch' },
  { id: 'invest', min: 80, max: 100, label: 'Invest', tone: 'strong' },
];

export const DEFAULT_VERDICT_BADGES: VerdictBadgeConfig[] = [
  { id: 'INVEST', label: 'Invest', backgroundColor: '#c3d3c9' },
  { id: 'MONITOR', label: 'Monitor', backgroundColor: '#cfccbb' },
  { id: 'PASS', label: 'Pass', backgroundColor: '#d6c4c0' },
  { id: 'STRONG', label: 'Strong', backgroundColor: '#c3d3c9' },
  { id: 'MEDIUM', label: 'Medium', backgroundColor: '#cfccbb' },
  { id: 'WEAK', label: 'Weak', backgroundColor: '#d6c4c0' },
];

export const VERDICT_BADGE_LABELS: Record<VerdictBadgeId, string> = DEFAULT_VERDICT_BADGES.reduce(
  (acc, badge) => ({ ...acc, [badge.id]: badge.label }),
  {} as Record<VerdictBadgeId, string>
);

export function createDefaultFundConfiguration(settings?: Settings | null): FundConfiguration {
  const identity = settings?.fund_identity;
  const base: FundConfiguration = {
    versionLabel: 'Fund Thesis v2',
    version: 1,
    lastSavedAt: null,
    activePolicyVersionId: null,
    draftPolicyHash: null,
    publishedPolicyHash: null,
    lastPublishedAt: null,
    mandate: {
      fundName: identity?.fund_name ?? '',
      mandateName: identity?.stage_focus ? `${identity.stage_focus} mandate` : 'Core mandate',
      preferredStages: parseList(identity?.stage_focus) || ['Pre-seed', 'Seed'],
      geographies: parseList(identity?.geographic_focus) || ['US', 'Europe'],
      customGeography: '',
      sectors: ['B2B SaaS', 'AI', 'Infrastructure'],
      customSectors: '',
      excludedSectors: '',
      businessModels: 'Enterprise SaaS, usage-based infrastructure, developer-led adoption',
      checkSizeMin: 250000,
      checkSizeMax: 1500000,
      ownershipTarget: 8,
      minimumTraction: 'Clear founder-market fit, credible early user pull, or strong technical wedge.',
      thesisText: '',
    },
    scoringWeights: DEFAULT_SCORING_WEIGHTS,
    scoreBands: DEFAULT_SCORE_BANDS,
    verdictBadges: DEFAULT_VERDICT_BADGES,
    thresholds: {
      autoPass: 39,
      monitor: 59,
      escalation: 75,
      partnerReview: 60,
      staleAfterHours: 48,
      confidenceFloor: normalizeConfidence(settings?.agent_config?.confidence_threshold) ?? 0.55,
      missingDataThreshold: 35,
    },
    risk: {
      sensitivity: 'balanced',
      requireAcknowledgement: true,
      onlyGateHighSeverity: true,
      missingFounderPenalty: 8,
      missingTractionPenalty: 7,
      contradictionPenalty: 12,
      weakSourcePenalty: 5,
    },
    memo: {
      style: settings?.portfolio?.memo_verbosity === 'minimal'
        ? 'concise'
        : settings?.portfolio?.memo_verbosity === 'full'
          ? 'detailed'
          : 'standard',
      deepDiveCollapsed: true,
      includeEvidenceExcerpts: true,
      includeMissingData: true,
      includeScoreReasoning: true,
      includeSourceConfidence: true,
      tone: 'partner',
    },
    rubric: createDefaultRubric(),
  };
  return settings?.fund_config ? mergeFundConfiguration(base, settings.fund_config) : base;
}

export function loadFundConfiguration(settings?: Settings | null): FundConfiguration {
  const backendConfig = settings?.fund_config;
  if (backendConfig) return createDefaultFundConfiguration(settings);
  if (typeof window === 'undefined') return createDefaultFundConfiguration(settings);
  const fallback = createDefaultFundConfiguration(settings);
  try {
    const raw = window.localStorage.getItem(FUND_CONFIG_STORAGE_KEY);
    if (!raw) return fallback;
    return mergeFundConfiguration(fallback, JSON.parse(raw) as Partial<FundConfiguration>);
  } catch {
    return fallback;
  }
}

export function saveFundConfiguration(config: FundConfiguration): FundConfiguration {
  const next = { ...config, lastSavedAt: new Date().toISOString() };
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(FUND_CONFIG_STORAGE_KEY, JSON.stringify(next));
    window.dispatchEvent(new CustomEvent(FUND_CONFIG_EVENT, { detail: next }));
  }
  return next;
}

export function clearFundConfiguration(settings?: Settings | null): FundConfiguration {
  const next = createDefaultFundConfiguration(settings);
  if (typeof window !== 'undefined') {
    window.localStorage.removeItem(FUND_CONFIG_STORAGE_KEY);
    window.dispatchEvent(new CustomEvent(FUND_CONFIG_EVENT, { detail: next }));
  }
  return next;
}

/** Mirrors backend `fund_config_raw_text` + `fund_config_to_thesis_parsed_json` for thesis sync. */
export function buildFundConfigThesisPayload(config: FundConfiguration): {
  raw_text: string;
  parsed_json: Record<string, unknown>;
} {
  const mandate = config.mandate;
  const sectors = [
    ...(mandate.preferredSectors ?? []),
    ...(mandate.sectors ?? []),
  ].map((item) => item.trim()).filter(Boolean);
  const geographies = [
    ...(mandate.geographyPreferences ?? []),
    ...(mandate.geographies ?? []),
    ...parseList(mandate.customGeography),
  ].map((item) => item.trim()).filter(Boolean);
  const exclusions = [
    ...(mandate.excludedSectorList ?? []),
    ...parseList(mandate.excludedSectors),
  ].map((item) => item.trim()).filter(Boolean);
  const preferences = [mandate.businessModels, mandate.minimumTraction, mandate.thesisText]
    .map((item) => item.trim())
    .filter(Boolean);
  const rawLines = [
    mandate.thesisText.trim(),
    `Preferred sectors: ${sectors.join(', ')}`,
    `Excluded sectors: ${exclusions.join(', ')}`,
    `Preferred stages: ${(mandate.preferredStages ?? []).join(', ')}`,
    `Geography: ${geographies.join(', ')}`,
    `Business models: ${mandate.businessModels || ''}`,
    `Minimum traction: ${mandate.minimumTraction || ''}`,
  ].filter((line) => line && !line.endsWith(': '));

  return {
    raw_text: rawLines.join('\n').trim(),
    parsed_json: {
      sectors,
      stage_focus: mandate.preferredStages ?? [],
      geography: geographies,
      preferences,
      exclusions,
      risk_profile: config.risk.sensitivity,
      check_size_min: mandate.checkSizeMin,
      check_size_max: mandate.checkSizeMax,
      ownership_target: mandate.ownershipTarget,
      score_bands: config.scoreBands,
      scoring_weights: config.scoringWeights,
      rubric: config.rubric,
      thresholds: config.thresholds,
      source: 'settings.fund_config',
    },
  };
}

export function mapFundConfigToSettings(config: FundConfiguration, settings: Settings): Settings {
  return {
    ...settings,
    fund_config: {
      ...config,
      mandate: {
        ...config.mandate,
        preferredSectors: [
          ...config.mandate.sectors,
          config.mandate.customSectors,
        ].map((item) => item.trim()).filter(Boolean),
        excludedSectorList: parseList(config.mandate.excludedSectors),
        geographyPreferences: [
          ...config.mandate.geographies,
          config.mandate.customGeography,
        ].map((item) => item.trim()).filter(Boolean),
      },
    },
    fund_identity: {
      ...(settings.fund_identity ?? { fund_name: '', stage_focus: '', geographic_focus: '' }),
      fund_name: config.mandate.fundName,
      stage_focus: joinList(config.mandate.preferredStages),
      geographic_focus: joinList([
        ...config.mandate.geographies,
        config.mandate.customGeography,
      ]),
    },
    agent_config: {
      ...settings.agent_config,
      confidence_threshold: config.thresholds.confidenceFloor,
    },
    portfolio: {
      ...settings.portfolio,
      memo_verbosity:
        config.memo.style === 'concise'
          ? 'minimal'
          : config.memo.style === 'detailed'
            ? 'full'
            : 'standard',
    },
  };
}

export function validateWeights(weights: ScoringWeight[]): WeightValidation {
  const total = Math.round(weights.reduce((sum, item) => sum + Number(item.weight || 0), 0) * 10) / 10;
  return { total, valid: Math.abs(total - 100) < 0.1, delta: Math.round((100 - total) * 10) / 10 };
}

/**
 * Set one weight and proportionally rebalance the others so the set always sums to
 * exactly 100. This powers the "auto-adjusting" feel: nudge one dimension and the
 * rest absorb the difference (equal split when the others are all zero). Integer
 * rounding drift is corrected against the largest fractional parts so totals are exact.
 */
export function rebalanceWeights(
  weights: ScoringWeight[],
  changedKey: ScoringDimensionKey,
  rawValue: number,
): ScoringWeight[] {
  const next = Math.min(100, Math.max(0, Math.round(Number(rawValue) || 0)));
  const others = weights.filter((w) => w.key !== changedKey);
  if (others.length === 0) return weights.map((w) => ({ ...w, weight: next }));

  const remaining = 100 - next;
  const othersTotal = others.reduce((sum, w) => sum + Math.max(0, w.weight), 0);
  const exact = others.map((w) =>
    othersTotal > 0 ? (Math.max(0, w.weight) / othersTotal) * remaining : remaining / others.length,
  );
  const rounded = exact.map((value) => Math.max(0, Math.round(value)));

  // Correct rounding drift by ±1 against the largest fractional parts (descending
  // for a deficit, ascending for a surplus) so the others fill `remaining` exactly.
  let drift = remaining - rounded.reduce((sum, r) => sum + r, 0);
  const fractionOrder = exact
    .map((value, index) => ({ index, frac: value - Math.floor(value) }))
    .sort((a, b) => (drift > 0 ? b.frac - a.frac : a.frac - b.frac));
  for (let i = 0; drift !== 0 && i < fractionOrder.length * 200; i += 1) {
    const idx = fractionOrder[i % fractionOrder.length].index;
    const step = drift > 0 ? 1 : -1;
    if (rounded[idx] + step < 0) continue;
    rounded[idx] += step;
    drift -= step;
  }

  const byKey = new Map(others.map((w, i) => [w.key, rounded[i]]));
  return weights.map((w) =>
    w.key === changedKey ? { ...w, weight: next } : { ...w, weight: byKey.get(w.key) ?? w.weight },
  );
}

export function normalizeWeights(weights: ScoringWeight[]): ScoringWeight[] {
  const total = weights.reduce((sum, item) => sum + Number(item.weight || 0), 0);
  if (total <= 0) return DEFAULT_SCORING_WEIGHTS;
  return weights.map((item, index) => {
    const raw = (item.weight / total) * 100;
    const rounded = index === weights.length - 1 ? raw : Math.round(raw);
    return { ...item, weight: Math.max(0, Math.round(rounded)) };
  }).map((item, index, all) => {
    if (index !== all.length - 1) return item;
    const prior = all.slice(0, -1).reduce((sum, w) => sum + w.weight, 0);
    return { ...item, weight: Math.max(0, 100 - prior) };
  });
}

export function validateScoreBands(bands: ScoreBand[]): BandValidation {
  const sorted = [...bands].sort((a, b) => a.min - b.min);
  const errors: string[] = [];
  sorted.forEach((band) => {
    if (band.min < 0 || band.max > 100) errors.push(`${band.label} must stay between 0 and 100.`);
    if (band.min > band.max) errors.push(`${band.label} starts after it ends.`);
  });
  for (let i = 1; i < sorted.length; i += 1) {
    if (sorted[i].min <= sorted[i - 1].max) {
      errors.push(`${sorted[i - 1].label} overlaps ${sorted[i].label}.`);
    }
    if (sorted[i].min > sorted[i - 1].max + 1) {
      errors.push(`Gap between ${sorted[i - 1].label} and ${sorted[i].label}.`);
    }
  }
  return { valid: errors.length === 0, errors };
}

export function bandForScore(score: number, bands: ScoreBand[]): ScoreBand {
  return bands.find((band) => score >= band.min && score <= band.max) ?? bands[bands.length - 1] ?? DEFAULT_SCORE_BANDS[0];
}

export function computeConfiguredScore(startup: Startup, config: FundConfiguration): number {
  const review = startup.review;
  const scores: Record<ScoringDimensionKey, number | null> = {
    market: review?.market_score ?? review?.structured_scoring?.market?.score ?? null,
    product: review?.product_score ?? review?.structured_scoring?.product?.score ?? null,
    technical: review?.technical_score ?? review?.structured_scoring?.technical?.score ?? null,
    execution: review?.execution_score ?? review?.structured_scoring?.execution?.score ?? null,
    defensibility: review?.defensibility_score ?? review?.structured_scoring?.defensibility?.score ?? null,
    traction: deriveTractionScore(startup),
    timing: deriveTimingScore(startup),
    fundFit: deriveFundFitScore(startup),
  };
  const available = config.scoringWeights.filter(
    (weight) =>
      scores[weight.key] != null
      && Number.isFinite(scores[weight.key])
      && Number.isFinite(weight.weight),
  );
  const fallback = Math.round((startup.scout.confidence ?? 0.5) * 100);
  if (!available.length) return fallback;
  const weighted = available.reduce((sum, weight) => sum + ((scores[weight.key] ?? 0) * 10 * weight.weight), 0);
  const totalWeight = available.reduce((sum, weight) => sum + weight.weight, 0);
  if (!(totalWeight > 0)) return fallback;
  const result = Math.round(weighted / totalWeight);
  return Number.isFinite(result) ? result : fallback;
}

export function isStartupStaleByConfig(startup: Startup, config: FundConfiguration, now = Date.now()): boolean {
  if (startup.human_resolution?.resolved_at) return false;
  const raw =
    startup.unresolved_at
    ?? startup.timestamps?.unresolved_at
    ?? startup.timestamps?.partnered_at
    ?? startup.timestamps?.reviewed_at
    ?? startup.timestamps?.discovered_at;
  if (!raw) return false;
  const time = new Date(raw).getTime();
  if (!Number.isFinite(time)) return false;
  return now - time >= Math.max(1, config.thresholds.staleAfterHours) * 60 * 60 * 1000;
}

export function shouldGateRisk(config: FundConfiguration, hasHighRisk: boolean, hasAnyRisk: boolean, isDecided: boolean): boolean {
  if (isDecided || !config.risk.requireAcknowledgement) return false;
  if (config.risk.onlyGateHighSeverity) return hasHighRisk;
  return config.risk.sensitivity === 'conservative' ? hasAnyRisk : hasHighRisk;
}

export function getWeightImpactText(key: ScoringDimensionKey): string {
  const impact: Record<ScoringDimensionKey, string> = {
    market: 'Higher weight emphasizes category size, growth trajectory, and buyer urgency in scoring.',
    product: 'Higher weight emphasizes product-market fit, user pull, and differentiation.',
    technical: 'Higher weight raises the bar for engineering depth, architecture quality, and data advantage.',
    execution: 'Higher weight emphasizes traction evidence, team caliber, and operational velocity.',
    defensibility: 'Higher weight emphasizes moats, switching costs, and compounding advantages.',
    traction: 'Sub-signal of Execution. Weight adjusts traction emphasis within execution scoring.',
    timing: 'Sub-signal of Market. Weight adjusts why-now emphasis within market scoring.',
    fundFit: 'Derived signal. Fund fit is computed from mandate alignment and does not participate in core scoring.',
  };
  return impact[key];
}

function mergeFundConfiguration(base: FundConfiguration, saved: Partial<FundConfiguration>): FundConfiguration {
  const mandate = normalizeMandate(base.mandate, saved.mandate);
  const mergedWeights = mergeCanonicalWeights(base.scoringWeights, saved.scoringWeights);
  return {
    ...base,
    ...saved,
    mandate,
    thresholds: { ...base.thresholds, ...saved.thresholds },
    risk: { ...base.risk, ...saved.risk },
    memo: { ...base.memo, ...saved.memo },
    scoringWeights: mergedWeights,
    scoreBands: normalizeScoreBands(saved.scoreBands),
    verdictBadges: normalizeVerdictBadges(saved.verdictBadges),
    rubric: saved.rubric?.length ? normalizeRubricCriteria(saved.rubric) : base.rubric,
  };
}

function mergeCanonicalWeights(base: ScoringWeight[], saved?: ScoringWeight[]): ScoringWeight[] {
  const savedMap = new Map((saved ?? []).map((item) => [item.key, item]));
  return base.map((item) => {
    const savedItem = savedMap.get(item.key);
    const canonical = CANONICAL_DIMENSIONS[item.key as CoreDimensionKey];
    // A corrupted saved config (non-numeric / NaN weight) must not propagate — it
    // would make computeConfiguredScore return NaN, and bandForScore(NaN) falls
    // through to the top band, mislabelling every startup "Invest". Coerce and
    // fall back to the canonical/base weight when the saved value isn't finite.
    const savedWeight = Number(savedItem?.weight);
    return {
      ...item,
      weight: Number.isFinite(savedWeight) ? savedWeight : item.weight,
      label: canonical?.label ?? item.label,
      description: canonical?.description ?? item.description,
    };
  });
}

export function badgeTextColorForBackground(backgroundColor: string): '#1a2b48' | '#fffdf7' {
  const hex = normalizeHexColor(backgroundColor);
  if (!hex) return '#1a2b48';
  const r = Number.parseInt(hex.slice(1, 3), 16) / 255;
  const g = Number.parseInt(hex.slice(3, 5), 16) / 255;
  const b = Number.parseInt(hex.slice(5, 7), 16) / 255;
  const luminance = [r, g, b]
    .map((channel) => channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4)
    .reduce((sum, channel, index) => sum + channel * [0.2126, 0.7152, 0.0722][index], 0);
  return luminance > 0.48 ? '#1a2b48' : '#fffdf7';
}

export function normalizeHexColor(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  if (/^#[0-9a-f]{6}$/i.test(trimmed)) return trimmed.toLowerCase();
  if (/^#[0-9a-f]{3}$/i.test(trimmed)) {
    return `#${trimmed[1]}${trimmed[1]}${trimmed[2]}${trimmed[2]}${trimmed[3]}${trimmed[3]}`.toLowerCase();
  }
  return null;
}

function normalizeVerdictBadges(saved?: VerdictBadgeConfig[]): VerdictBadgeConfig[] {
  const savedMap = new Map((saved ?? []).map((badge) => [badge.id, badge]));
  return DEFAULT_VERDICT_BADGES.map((badge) => {
    const savedBadge = savedMap.get(badge.id);
    const backgroundColor = normalizeHexColor(savedBadge?.backgroundColor) ?? badge.backgroundColor;
    return { ...badge, backgroundColor };
  });
}

function normalizeScoreBands(saved?: ScoreBand[]): ScoreBand[] {
  if (saved?.some((band) => ['review', 'escalate', 'strong'].includes(band.id)) || !saved?.some((band) => band.id === 'invest')) {
    return DEFAULT_SCORE_BANDS;
  }
  const savedMap = new Map((saved ?? []).map((band) => [band.id, band]));
  return DEFAULT_SCORE_BANDS.map((band) => {
    const savedBand = savedMap.get(band.id);
    return {
      ...band,
      min: clampPercentage(savedBand?.min ?? band.min),
      max: clampPercentage(savedBand?.max ?? band.max),
    };
  });
}

function clampPercentage(value: unknown): number {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 0;
  return Math.max(0, Math.min(100, Math.round(numeric)));
}

function normalizeMandate(base: FundMandateConfig, saved?: Partial<FundMandateConfig>): FundMandateConfig {
  const mandate = { ...base, ...saved };
  const preferredSectors = toList(saved?.preferredSectors ?? mandate.preferredSectors);
  const savedSectors = toList(saved?.sectors);
  const explicitCustomSectors = toList(saved?.customSectors ?? mandate.customSectors);
  const sectorSource = savedSectors.length
    ? savedSectors
    : preferredSectors.length
      ? preferredSectors
      : toList(base.sectors);
  const sectors = sectorSource.filter((item) => KNOWN_SECTOR_OPTIONS.has(item));
  const customSectors = explicitCustomSectors.length
    ? joinList(explicitCustomSectors)
    : joinList(sectorSource.filter((item) => !KNOWN_SECTOR_OPTIONS.has(item)));

  const geographyPreferences = toList(saved?.geographyPreferences ?? mandate.geographyPreferences);
  const savedGeographies = toList(saved?.geographies);
  const explicitCustomGeography = toList(saved?.customGeography ?? mandate.customGeography);
  const geographySource = savedGeographies.length
    ? savedGeographies
    : geographyPreferences.length
      ? geographyPreferences
      : toList(base.geographies);
  const geographies = geographySource.filter((item) => KNOWN_GEOGRAPHY_OPTIONS.has(item));
  const customGeography = explicitCustomGeography.length
    ? joinList(explicitCustomGeography)
    : joinList(geographySource.filter((item) => !KNOWN_GEOGRAPHY_OPTIONS.has(item)));

  const excludedSectorList = toList(saved?.excludedSectorList ?? mandate.excludedSectorList);
  const savedExcludedSectors = toList(saved?.excludedSectors);
  const excludedSectors = joinList(savedExcludedSectors.length ? savedExcludedSectors : excludedSectorList);

  return {
    ...mandate,
    preferredSectors,
    excludedSectorList,
    geographyPreferences,
    sectors,
    customSectors,
    geographies,
    customGeography,
    excludedSectors,
  };
}

function createDefaultRubric(): RubricCriterion[] {
  return CANONICAL_DIMENSION_KEYS.map((key) => {
    const dim = CANONICAL_DIMENSIONS[key];
    const bands = DIMENSION_SCORE_BANDS[key];
    return {
      id: `${key}-core`,
      dimension: key,
      name: `${dim.label} conviction`,
      description: dim.description,
      weight: 100,
      positiveSignals: 'Clear, evidence-backed signal that compounds with the fund mandate.',
      negativeSignals: 'Unresolved weakness, shallow evidence, or signal that contradicts the mandate.',
      missingDataBehavior: 'Treat as diligence debt and reduce conviction until evidence is supplied.',
      examples: {
        score3: bands[3],
        score5: bands[5],
        score7: bands[7],
        score9: bands[9],
      },
    };
  });
}

function normalizeRubricCriteria(rubric: RubricCriterion[]): RubricCriterion[] {
  const dimensionMap: Partial<Record<ScoringDimensionKey, ScoringDimensionKey>> = {
    traction: 'execution',
    timing: 'market',
    fundFit: 'defensibility',
  };
  const allowed = new Set<ScoringDimensionKey>(DEFAULT_SCORING_WEIGHTS.map((item) => item.key));
  return rubric.map((item) => {
    const dimension = dimensionMap[item.dimension] ?? item.dimension;
    return {
      ...item,
      dimension: allowed.has(dimension) ? dimension : 'market',
    };
  });
}

function parseList(value?: string): string[] {
  return (value ?? '')
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinList(values: string[]): string {
  return values.map((item) => item.trim()).filter(Boolean).join(', ');
}

function toList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.flatMap((item) => toList(item));
  }
  if (typeof value === 'string') return parseList(value);
  return [];
}

function normalizeConfidence(value: unknown): number | null {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  return Math.max(0, Math.min(1, numeric));
}

function deriveTractionScore(startup: Startup): number | null {
  const text = [
    startup.partner?.traction_signals,
    startup.scout.primary_thesis,
    startup.review?.business_model_analysis?.join(' '),
  ].filter(Boolean).join(' ').toLowerCase();
  if (!text.trim()) return null;
  if (/(revenue|arr|retention|paid|enterprise|pilot|customer|usage|growth)/.test(text)) return 7;
  if (/(waitlist|beta|prototype|early)/.test(text)) return 5;
  return 4;
}

function deriveTimingScore(startup: Startup): number | null {
  const whyNow = startup.scout.why_now?.trim();
  if (!whyNow) return null;
  return whyNow.length > 180 ? 7 : 5;
}

function deriveFundFitScore(startup: Startup): number | null {
  const score = startup.review?.thesis_alignment_score ?? startup.review?.fund_thesis_alignment_score;
  if (typeof score === 'number' && Number.isFinite(score)) {
    return score <= 1 ? Math.round(score * 10) : Math.min(10, score);
  }
  if (startup.review?.thesis_matches_fund === true) return 8;
  if (startup.review?.thesis_matches_fund === false) return 3;
  return null;
}
