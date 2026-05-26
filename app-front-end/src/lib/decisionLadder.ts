import { bandForScore, type FundConfiguration, type ScoreBand } from './fundConfiguration';

export interface DecisionLadderBoundaries {
  /** Scores below this (0–100) are weakest borderline / auto-pass lean in Partner policy. */
  autoPassCeiling: number;
  /** Weighted score and Partner pass bar: at or above → Monitor band (Partner avg ÷ 10). */
  passMonitorBoundary: number;
  /** At or above → Invest band and strong-yes Partner bar. */
  monitorInvestBoundary: number;
}

export interface LadderValidation {
  valid: boolean;
  errors: string[];
}

function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n));
}

function passBand(config: FundConfiguration): ScoreBand | undefined {
  return config.scoreBands.find((band) => band.id === 'pass');
}

function investBand(config: FundConfiguration): ScoreBand | undefined {
  return config.scoreBands.find((band) => band.id === 'invest');
}

/** Read ladder boundaries; thresholds are canonical when present. */
export function getDecisionLadderBoundaries(config: FundConfiguration): DecisionLadderBoundaries {
  const { thresholds } = config;
  const pass = passBand(config);
  const invest = investBand(config);
  const passMonitorBoundary = thresholds.partnerReview
    ?? (pass ? pass.max + 1 : 60);
  const monitorInvestBoundary = thresholds.escalation
    ?? (invest ? invest.min : 80);
  const autoPassCeiling = thresholds.autoPass
    ?? (pass ? Math.min(pass.max, 39) : 39);
  return {
    autoPassCeiling: clamp(Math.round(autoPassCeiling), 0, 98),
    passMonitorBoundary: clamp(Math.round(passMonitorBoundary), 1, 99),
    monitorInvestBoundary: clamp(Math.round(monitorInvestBoundary), 2, 100),
  };
}

export function isDecisionLadderDrifted(config: FundConfiguration): boolean {
  const ladder = getDecisionLadderBoundaries(config);
  const pass = passBand(config);
  const monitor = config.scoreBands.find((band) => band.id === 'monitor');
  const invest = investBand(config);
  if (!pass || !monitor || !invest) return false;
  const passMax = ladder.passMonitorBoundary - 1;
  const monitorMax = ladder.monitorInvestBoundary - 1;
  return (
    pass.max !== passMax
    || monitor.min !== ladder.passMonitorBoundary
    || monitor.max !== monitorMax
    || invest.min !== ladder.monitorInvestBoundary
    || config.thresholds.monitor !== monitorMax
  );
}

export function validateDecisionLadder(config: FundConfiguration): LadderValidation {
  const { autoPassCeiling, passMonitorBoundary, monitorInvestBoundary } = getDecisionLadderBoundaries(config);
  const errors: string[] = [];
  if (passMonitorBoundary >= monitorInvestBoundary) {
    errors.push('Pass → Monitor boundary must be lower than Monitor → Invest boundary.');
  }
  if (autoPassCeiling >= passMonitorBoundary) {
    errors.push('Weak-deal ceiling must stay below the Pass → Monitor boundary.');
  }
  if (monitorInvestBoundary > 100 || passMonitorBoundary < 1) {
    errors.push('Boundaries must keep all three bands within 0–100.');
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

/** Apply ladder edits: keeps Partner thresholds and grid score bands aligned. */
export function applyDecisionLadder(
  config: FundConfiguration,
  patch: Partial<DecisionLadderBoundaries>,
): FundConfiguration {
  const current = getDecisionLadderBoundaries(config);
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
  let autoPassCeiling = clamp(
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

export function formatReviewerScale(score0to100: number): string {
  return (score0to100 / 10).toFixed(1);
}

export interface LadderPreviewExample {
  weightedScore: number;
  gridLabel: string;
  reviewerAvg: number;
  partnerNote: string;
}

export function buildLadderPreviewExamples(config: FundConfiguration): LadderPreviewExample[] {
  const { autoPassCeiling, passMonitorBoundary, monitorInvestBoundary } = getDecisionLadderBoundaries(config);
  const midPass = Math.max(0, Math.floor(autoPassCeiling / 2));
  const midMonitor = Math.floor((passMonitorBoundary + monitorInvestBoundary) / 2);
  const midInvest = Math.min(100, monitorInvestBoundary + 8);

  const examples: Array<{ weightedScore: number; reviewerAvg: number }> = [
    { weightedScore: midPass, reviewerAvg: autoPassCeiling / 10 },
    { weightedScore: passMonitorBoundary, reviewerAvg: passMonitorBoundary / 10 },
    { weightedScore: midMonitor, reviewerAvg: midMonitor / 10 },
    { weightedScore: midInvest, reviewerAvg: monitorInvestBoundary / 10 },
  ];

  return examples.map(({ weightedScore, reviewerAvg }) => ({
    weightedScore,
    reviewerAvg,
    gridLabel: bandForScore(weightedScore, config.scoreBands).label,
    partnerNote: describePartnerPath(reviewerAvg, config),
  }));
}

function describePartnerPath(reviewerAvg: number, config: FundConfiguration): string {
  const { autoPassCeiling, passMonitorBoundary, monitorInvestBoundary } = getDecisionLadderBoundaries(config);
  const passBar = passMonitorBoundary / 10;
  const monitorTop = (monitorInvestBoundary - 1) / 10;
  const investBar = monitorInvestBoundary / 10;
  const autoBar = autoPassCeiling / 10;

  if (reviewerAvg < autoBar) return 'Partner leans pass (weak borderline band).';
  if (reviewerAvg < passBar) return 'Partner below funnel bar — likely pass unless other rules fire.';
  if (reviewerAvg < monitorTop) return 'Partner monitor / maybe path.';
  if (reviewerAvg < investBar) return 'Partner upper monitor band.';
  return 'Partner strong-candidate / invest-grade bar.';
}
