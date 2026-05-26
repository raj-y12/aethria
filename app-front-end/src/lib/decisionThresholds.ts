import { type FundConfiguration, type ScoreBand } from './fundConfiguration';

export interface DecisionThresholdBoundaries {
  autoPassCeiling: number;
  passMonitorBoundary: number;
  monitorInvestBoundary: number;
}

export interface ThresholdValidation {
  valid: boolean;
  errors: string[];
}

function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n));
}

function parseScore(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number.parseInt(trimmed, 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function passBand(config: FundConfiguration): ScoreBand | undefined {
  return config.scoreBands.find((band) => band.id === 'pass');
}

function investBand(config: FundConfiguration): ScoreBand | undefined {
  return config.scoreBands.find((band) => band.id === 'invest');
}

export function getDecisionThresholdBoundaries(config: FundConfiguration): DecisionThresholdBoundaries {
  const { thresholds } = config;
  const pass = passBand(config);
  const invest = investBand(config);
  const passMonitorBoundary = thresholds.partnerReview ?? (pass ? pass.max + 1 : 60);
  const monitorInvestBoundary = thresholds.escalation ?? (invest ? invest.min : 80);
  const autoPassCeiling = thresholds.autoPass ?? (pass ? Math.min(pass.max, 39) : 39);
  return {
    autoPassCeiling: clamp(Math.round(autoPassCeiling), 0, 98),
    passMonitorBoundary: clamp(Math.round(passMonitorBoundary), 1, 99),
    monitorInvestBoundary: clamp(Math.round(monitorInvestBoundary), 2, 100),
  };
}

export function isDecisionThresholdDrifted(config: FundConfiguration): boolean {
  const bounds = getDecisionThresholdBoundaries(config);
  const pass = passBand(config);
  const monitor = config.scoreBands.find((band) => band.id === 'monitor');
  const invest = investBand(config);
  if (!pass || !monitor || !invest) return false;
  const passMax = bounds.passMonitorBoundary - 1;
  const monitorMax = bounds.monitorInvestBoundary - 1;
  return (
    pass.max !== passMax
    || monitor.min !== bounds.passMonitorBoundary
    || monitor.max !== monitorMax
    || invest.min !== bounds.monitorInvestBoundary
    || config.thresholds.monitor !== monitorMax
  );
}

export function validateDecisionThresholds(config: FundConfiguration): ThresholdValidation {
  const { autoPassCeiling, passMonitorBoundary, monitorInvestBoundary } = getDecisionThresholdBoundaries(config);
  const errors: string[] = [];
  if (passMonitorBoundary >= monitorInvestBoundary) {
    errors.push('Monitor must start below Invest.');
  }
  if (autoPassCeiling >= passMonitorBoundary) {
    errors.push('Auto-pass must stay below where Monitor starts.');
  }
  return { valid: errors.length === 0, errors };
}

function syncScoreBands(
  bands: ScoreBand[],
  passMax: number,
  monitorMin: number,
  monitorMax: number,
  investMin: number,
): ScoreBand[] {
  return bands.map((band) => {
    if (band.id === 'pass') return { ...band, min: 0, max: passMax };
    if (band.id === 'monitor') return { ...band, min: monitorMin, max: monitorMax };
    if (band.id === 'invest') return { ...band, min: investMin, max: 100 };
    return band;
  });
}

export function applyDecisionThresholds(
  config: FundConfiguration,
  patch: Partial<DecisionThresholdBoundaries>,
): FundConfiguration {
  const current = getDecisionThresholdBoundaries(config);
  let passMonitorBoundary = clamp(
    Math.round(patch.passMonitorBoundary ?? current.passMonitorBoundary),
    1,
    99,
  );
  let monitorInvestBoundary = clamp(
    Math.round(patch.monitorInvestBoundary ?? current.monitorInvestBoundary),
    2,
    100,
  );
  if (monitorInvestBoundary <= passMonitorBoundary) {
    monitorInvestBoundary = Math.min(100, passMonitorBoundary + 1);
  }

  const passMax = passMonitorBoundary - 1;
  const autoPassCeiling = clamp(
    Math.round(patch.autoPassCeiling ?? current.autoPassCeiling),
    0,
    Math.max(0, passMax),
  );
  const monitorMin = passMonitorBoundary;
  const monitorMax = monitorInvestBoundary - 1;

  return {
    ...config,
    thresholds: {
      ...config.thresholds,
      autoPass: autoPassCeiling,
      partnerReview: passMonitorBoundary,
      monitor: monitorMax,
      escalation: monitorInvestBoundary,
    },
    scoreBands: syncScoreBands(config.scoreBands, passMax, monitorMin, monitorMax, monitorInvestBoundary),
  };
}

export function formatReviewerAvg(score0to100: number): string {
  return (score0to100 / 10).toFixed(1);
}

/** Parse and clamp a 0–100 score field from user input. */
export function commitScoreInput(raw: string, min: number, max: number, fallback: number): number {
  const parsed = parseScore(raw);
  if (parsed == null) return fallback;
  return clamp(parsed, min, max);
}

export const DEFAULT_DECISION_BOUNDARIES: DecisionThresholdBoundaries = {
  passMonitorBoundary: 60,
  monitorInvestBoundary: 80,
  autoPassCeiling: 39,
};
