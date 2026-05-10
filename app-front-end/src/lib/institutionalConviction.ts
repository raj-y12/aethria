import type { DecisionHistoryRecord, Startup } from '../types/startup';
import { extractAdverseRegister } from './adverseRegister';
import { computeConfiguredScore, isStartupStaleByConfig, type FundConfiguration } from './fundConfiguration';
import { isDealDecided } from './dealState';

export interface CalibrationObservation {
  label: string;
  value: string | number;
  detail?: string;
}

export interface FundIntelligenceSnapshot {
  observations: CalibrationObservation[];
  commonRiskThemes: Array<{ theme: string; count: number }>;
  decisionsByOutcome: Record<'YES' | 'NO' | 'MAYBE', number>;
  averageScore: number | null;
  pendingDecisions: number;
  staleDeals: number;
  escalatedDeals: number;
}

export interface PrecedentCandidate {
  startupId: string;
  name: string;
  decision: DecisionHistoryRecord['new_decision'];
  rationale?: string | null;
  timestamp: string;
  matchReasons: string[];
}

export function buildFundIntelligenceSnapshot(
  startups: Startup[],
  config: FundConfiguration
): FundIntelligenceSnapshot {
  const pending = startups.filter((startup) => !isDealDecided(startup));
  const decided = startups.filter((startup) => startup.human_resolution?.decision);
  const scores = startups
    .map((startup) => computeConfiguredScore(startup, config))
    .filter((score) => Number.isFinite(score));
  const riskCounts = new Map<string, number>();
  startups.forEach((startup) => {
    extractAdverseRegister(startup).forEach((item) => {
      const theme = item.title.trim();
      if (!theme) return;
      riskCounts.set(theme, (riskCounts.get(theme) ?? 0) + 1);
    });
  });

  const decisionsByOutcome = decided.reduce<Record<'YES' | 'NO' | 'MAYBE', number>>(
    (acc, startup) => {
      const decision = startup.human_resolution?.decision;
      if (decision) acc[decision] += 1;
      return acc;
    },
    { YES: 0, NO: 0, MAYBE: 0 }
  );

  const staleDeals = pending.filter((startup) => isStartupStaleByConfig(startup, config)).length;
  const escalatedDeals = pending.filter((startup) => startup.partner?.human_review_required).length;
  const averageScore = scores.length
    ? Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length)
    : null;

  return {
    observations: [
      { label: 'Pending decisions', value: pending.length },
      { label: 'Stale deals', value: staleDeals, detail: `${config.thresholds.staleAfterHours}h threshold` },
      { label: 'Escalated deals', value: escalatedDeals },
      { label: 'Average configured score', value: averageScore ?? '—' },
    ],
    commonRiskThemes: [...riskCounts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([theme, count]) => ({ theme, count })),
    decisionsByOutcome,
    averageScore,
    pendingDecisions: pending.length,
    staleDeals,
    escalatedDeals,
  };
}

export function findPrecedentCandidates(
  current: Startup,
  startups: Startup[],
  limit = 3
): PrecedentCandidate[] {
  const currentSector = normalize(current.scout.sector);
  const currentStage = normalize(current.scout.funding_stage);
  return startups
    .filter((startup) => startup.id !== current.id && startup.human_resolution?.decision)
    .map((startup) => {
      const matchReasons: string[] = [];
      if (currentSector && normalize(startup.scout.sector) === currentSector) matchReasons.push('sector');
      if (currentStage && normalize(startup.scout.funding_stage) === currentStage) matchReasons.push('stage');
      if (
        current.partner?.recommendation &&
        startup.partner?.recommendation &&
        current.partner.recommendation === startup.partner.recommendation
      ) {
        matchReasons.push('recommendation');
      }
      const history = startup.conviction_state?.decision_history ?? [];
      const latest = history[history.length - 1];
      return {
        startup,
        latest,
        matchReasons,
      };
    })
    .filter((item) => item.matchReasons.length > 0)
    .sort((a, b) => b.matchReasons.length - a.matchReasons.length)
    .slice(0, limit)
    .map(({ startup, latest, matchReasons }) => ({
      startupId: startup.id,
      name: startup.scout.name || startup.id,
      decision: startup.human_resolution?.decision ?? latest?.new_decision ?? 'MAYBE',
      rationale: latest?.rationale ?? startup.human_resolution?.notes ?? null,
      timestamp: latest?.timestamp ?? startup.human_resolution?.resolved_at ?? '',
      matchReasons,
    }));
}

function normalize(value: unknown): string {
  return String(value ?? '').trim().toLowerCase();
}
