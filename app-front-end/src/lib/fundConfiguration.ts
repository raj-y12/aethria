import type { Settings } from '../api/settings';
import type { Startup } from '../types/startup';

export type ScoringDimensionKey =
  | 'market'
  | 'product'
  | 'technical'
  | 'execution'
  | 'defensibility'
  | 'traction'
  | 'timing'
  | 'fundFit';

export type DecisionLabel = 'Pass' | 'Monitor' | 'Review' | 'Escalate' | 'Strong Proceed';
export type RiskSensitivity = 'conservative' | 'balanced' | 'aggressive';
export type MemoStyle = 'concise' | 'standard' | 'detailed';
export type MemoTone = 'partner' | 'analyst';

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
  mandate: FundMandateConfig;
  scoringWeights: ScoringWeight[];
  scoreBands: ScoreBand[];
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

const dimensionDescriptions: Record<ScoringDimensionKey, string> = {
  market: 'Market size, urgency, budget, and category expansion.',
  product: 'Strength of product insight, user pull, and workflow fit.',
  technical: 'Technical depth, feasibility, and defensible implementation.',
  execution: 'Founder quality, speed, operating maturity, and learning rate.',
  defensibility: 'Moats, distribution leverage, data advantage, and switching costs.',
  traction: 'Usage, revenue, retention, references, and repeatability.',
  timing: 'Why this company can win now rather than later.',
  fundFit: 'Alignment with mandate, ownership model, geography, and portfolio construction.',
};

export const DEFAULT_SCORING_WEIGHTS: ScoringWeight[] = [
  { key: 'market', label: 'Market', description: dimensionDescriptions.market, weight: 20 },
  { key: 'product', label: 'Product', description: dimensionDescriptions.product, weight: 20 },
  { key: 'technical', label: 'Technical', description: dimensionDescriptions.technical, weight: 20 },
  { key: 'execution', label: 'Execution', description: dimensionDescriptions.execution, weight: 20 },
  { key: 'defensibility', label: 'Defensibility', description: dimensionDescriptions.defensibility, weight: 20 },
];

export const DEFAULT_SCORE_BANDS: ScoreBand[] = [
  { id: 'pass', min: 0, max: 39, label: 'Pass', tone: 'negative' },
  { id: 'monitor', min: 40, max: 59, label: 'Monitor', tone: 'watch' },
  { id: 'review', min: 60, max: 74, label: 'Review', tone: 'review' },
  { id: 'escalate', min: 75, max: 89, label: 'Escalate', tone: 'positive' },
  { id: 'strong', min: 90, max: 100, label: 'Strong Proceed', tone: 'strong' },
];

export function createDefaultFundConfiguration(settings?: Settings | null): FundConfiguration {
  const identity = settings?.fund_identity;
  const base: FundConfiguration = {
    versionLabel: 'Fund Thesis v2',
    version: 1,
    lastSavedAt: null,
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
  const available = config.scoringWeights.filter((weight) => scores[weight.key] != null && Number.isFinite(scores[weight.key]));
  if (!available.length) return Math.round((startup.scout.confidence ?? 0.5) * 100);
  const weighted = available.reduce((sum, weight) => sum + ((scores[weight.key] ?? 0) * 10 * weight.weight), 0);
  const totalWeight = available.reduce((sum, weight) => sum + weight.weight, 0);
  return Math.round(weighted / totalWeight);
}

export function isStartupStaleByConfig(startup: Startup, config: FundConfiguration, now = Date.now()): boolean {
  if (startup.human_resolution?.resolved_at) return false;
  const raw = startup.timestamps?.partnered_at ?? startup.timestamps?.reviewed_at ?? startup.timestamps?.discovered_at;
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
    market: 'Increasing Market weight makes category size and urgency more influential in final recommendation.',
    product: 'Increasing Product weight rewards sharp user pull and workflow fit.',
    technical: 'Increasing Technical weight raises the bar for implementation depth and technical edge.',
    execution: 'Increasing Execution weight makes team quality more influential in final recommendation.',
    defensibility: 'Increasing Defensibility weight favors companies with compounding moats.',
    traction: 'Increasing Traction weight makes evidence of demand harder to ignore.',
    timing: 'Increasing Timing weight favors why-now inflections over evergreen markets.',
    fundFit: 'Increasing Fund Fit weight makes mandate alignment and portfolio construction more decisive.',
  };
  return impact[key];
}

function mergeFundConfiguration(base: FundConfiguration, saved: Partial<FundConfiguration>): FundConfiguration {
  return {
    ...base,
    ...saved,
    mandate: { ...base.mandate, ...saved.mandate },
    thresholds: { ...base.thresholds, ...saved.thresholds },
    risk: { ...base.risk, ...saved.risk },
    memo: { ...base.memo, ...saved.memo },
    scoringWeights: mergeByKey(base.scoringWeights, saved.scoringWeights, 'key'),
    scoreBands: mergeByKey(base.scoreBands, saved.scoreBands, 'id'),
    rubric: saved.rubric?.length ? normalizeRubricCriteria(saved.rubric) : base.rubric,
  };
}

function mergeByKey<T, K extends keyof T>(
  base: T[],
  saved: T[] | undefined,
  key: K
): T[] {
  if (!saved?.length) return base;
  const savedMap = new Map(saved.map((item) => [item[key], item]));
  return base.map((item) => ({ ...item, ...(savedMap.get(item[key]) ?? {}) }));
}

function createDefaultRubric(): RubricCriterion[] {
  return DEFAULT_SCORING_WEIGHTS.map((dimension) => ({
    id: `${dimension.key}-core`,
    dimension: dimension.key,
    name: `${dimension.label} conviction`,
    description: dimension.description,
    weight: 100,
    positiveSignals: 'Clear, evidence-backed signal that compounds with the fund mandate.',
    negativeSignals: 'Unresolved weakness, shallow evidence, or signal that contradicts the mandate.',
    missingDataBehavior: 'Treat as diligence debt and reduce conviction until evidence is supplied.',
    examples: {
      score3: 'Structurally weak or unsupported by evidence.',
      score5: 'Plausible but not yet differentiated.',
      score7: 'Strong signal with some diligence still open.',
      score9: 'Exceptional signal, well evidenced, and hard to replicate.',
    },
  }));
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
