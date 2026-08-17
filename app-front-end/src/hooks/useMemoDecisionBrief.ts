import { useQuery } from '@tanstack/react-query';
import { fetchOpportunityByLegacyStartup, type Opportunity } from '../api/identity';
import { fetchEvidenceLedger, type EvidenceLedger } from '../api/evidence';
import { fetchCurrentEvaluation, type EvaluationRecord, type RecommendationState } from '../api/evaluations';
import { listHumanRulings, type HumanRuling } from '../api/decisions';
import { buildMemoDecisionBrief, type MemoDecisionBrief } from '../lib/memoDecisionBrief';

function nestedString(value: unknown, key: string): string | null {
  if (!value || typeof value !== 'object') return null;
  const candidate = (value as Record<string, unknown>)[key];
  return typeof candidate === 'string' ? candidate : null;
}

export interface UseMemoDecisionBriefResult {
  opportunity: Opportunity | null | undefined;
  evidence: EvidenceLedger | undefined;
  evaluation: EvaluationRecord | undefined;
  rulings: HumanRuling[] | undefined;
  brief: MemoDecisionBrief;
  stateMessage: string | undefined;
  recommendationId: string | null;
  recommendedDecision: RecommendationState | null;
  hasClaims: boolean;
  decisionLoading: boolean;
  decisionUnavailable: boolean;
  canCompose: boolean;
  opportunityError: boolean;
  rulingsError: boolean;
}

/** Shared across the masthead verdict and the decision workspace so both read
 * the same canonical opportunity/evaluation/evidence/ruling queries — React
 * Query dedupes identical keys, so this is one fetch, not two. */
export function useMemoDecisionBrief(startupId: string): UseMemoDecisionBriefResult {
  const opportunity = useQuery({
    queryKey: ['institutional', 'opportunity', 'legacy', startupId],
    queryFn: () => fetchOpportunityByLegacyStartup(startupId),
    enabled: Boolean(startupId),
    staleTime: 30_000,
  });
  const opportunityId = opportunity.data?.opportunity_id;
  const evidence = useQuery({
    queryKey: ['institutional', 'evidence', opportunityId],
    queryFn: () => fetchEvidenceLedger(opportunityId!),
    enabled: Boolean(opportunityId),
    staleTime: 15_000,
  });
  const evaluation = useQuery({
    queryKey: ['institutional', 'evaluation', opportunityId],
    queryFn: () => fetchCurrentEvaluation(opportunityId!),
    enabled: Boolean(opportunityId),
    retry: false,
    staleTime: 15_000,
  });
  const rulings = useQuery({
    queryKey: ['institutional', 'rulings', opportunityId],
    queryFn: () => listHumanRulings(opportunityId!),
    enabled: Boolean(opportunityId),
    staleTime: 10_000,
  });

  const recommendationId = opportunity.data?.current_recommendation_id
    ?? nestedString(evaluation.data?.recommendation, 'recommendation_id');
  const recommendedDecision: RecommendationState | null =
    evaluation.data?.recommendation?.recommended_state ?? null;

  const hasClaims = Boolean(evidence.data?.claims.some((claim) => claim.status === 'current'));
  const decisionLoading = opportunity.isLoading
    || (Boolean(opportunityId) && (evaluation.isLoading || evidence.isLoading || rulings.isLoading));
  const decisionUnavailable = opportunity.isError
    || (!opportunity.isLoading && !opportunity.data)
    || evaluation.isError
    || evidence.isError
    || rulings.isError
    || (Boolean(opportunityId) && !evaluation.isLoading && !evaluation.data)
    || (Boolean(opportunityId) && !evidence.isLoading && !evidence.data);
  const brief = buildMemoDecisionBrief({
    evaluation: evaluation.data,
    ledger: evidence.data,
    ruling: rulings.data?.[0],
    loading: decisionLoading,
    unavailable: decisionUnavailable,
  });
  const stateMessage = decisionLoading
    ? 'Loading the canonical evaluation and evidence ledger.'
    : opportunity.isError || (!opportunity.isLoading && !opportunity.data)
      ? 'The opportunity-to-decision record link is unavailable.'
      : evaluation.isError || !evaluation.data
        ? 'The canonical evaluation could not be loaded.'
        : evidence.isError || !evidence.data
          ? 'The evidence ledger could not be loaded.'
          : rulings.isError
            ? 'The ruling history could not be loaded.'
            : brief.coverage === 'missing'
              ? 'The canonical evaluation is blocked by missing evidence.'
              : brief.coverage === 'contradictory'
                ? 'The canonical evaluation is blocked by contradictory evidence.'
                : undefined;
  const canCompose = Boolean(opportunity.data) && !decisionLoading && !decisionUnavailable;

  return {
    opportunity: opportunity.data,
    evidence: evidence.data,
    evaluation: evaluation.data,
    rulings: rulings.data,
    brief,
    stateMessage,
    recommendationId,
    recommendedDecision,
    hasClaims,
    decisionLoading,
    decisionUnavailable,
    canCompose,
    opportunityError: opportunity.isError || (!opportunity.isLoading && !opportunity.data),
    rulingsError: rulings.isError,
  };
}
