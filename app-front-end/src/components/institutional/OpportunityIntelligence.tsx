import { useQuery } from '@tanstack/react-query';
import { fetchOpportunityByLegacyStartup } from '../../api/identity';
import { fetchEvidenceLedger } from '../../api/evidence';
import { fetchCurrentEvaluation, type RecommendationState } from '../../api/evaluations';
import {
  listHumanRulings,
  type HumanRuling,
  type HumanRulingRecordDecision,
} from '../../api/decisions';
import { buildMemoDecisionBrief } from '../../lib/memoDecisionBrief';
import MemoDecisionBrief from '../memo/MemoDecisionBrief';
import ClaimEvidenceLedger from './ClaimEvidenceLedger';
import HumanRulingComposer from './HumanRulingComposer';

function nestedString(value: unknown, key: string): string | null {
  if (!value || typeof value !== 'object') return null;
  const candidate = (value as Record<string, unknown>)[key];
  return typeof candidate === 'string' ? candidate : null;
}

function decisionLabel(decision: HumanRulingRecordDecision): string {
  return decision.charAt(0).toUpperCase() + decision.slice(1);
}

function plainLabel(value: string): string {
  const words = value.replace(/_/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function rulingDate(value?: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(date);
}

function RulingHistory({ rulings }: { rulings: HumanRuling[] }) {
  if (rulings.length === 0) return null;
  const [latest, ...earlier] = rulings;
  return (
    <section className="memoDecisionHistory" aria-label="Ruling history">
      <div className="memoDecisionHistoryHead">
        <p className="memoDecisionEyebrow">Latest recorded ruling</p>
        <p className="memoDecisionHistoryDecision">{decisionLabel(latest.decision)}</p>
      </div>
      <p className="memoDecisionHistoryRationale">{latest.rationale}</p>
      <p className="memoDecisionMeta">{rulingDate(latest.created_at) ?? 'Recorded'}</p>
      {latest.override_type ? (
        <p className="memoDecisionOverride">Why it differs <span>{plainLabel(latest.override_type)}</span></p>
      ) : null}
      {earlier.length > 0 ? (
        <details className="memoDecisionDisclosure memoDecisionDisclosure--compact">
          <summary>View earlier rulings ({earlier.length})</summary>
          <ol className="memoDecisionHistoryList">
            {earlier.map((ruling) => (
              <li key={ruling.ruling_id}>
                <span>{decisionLabel(ruling.decision)}</span>
                <p>{ruling.rationale}</p>
                {ruling.override_type ? <em>Why it differs: {plainLabel(ruling.override_type)}</em> : null}
                <small>{rulingDate(ruling.created_at) ?? 'Recorded'}</small>
              </li>
            ))}
          </ol>
        </details>
      ) : null}
    </section>
  );
}

export default function OpportunityIntelligence({
  startupId,
  companyName = null,
  onRulingRecorded,
  readOnly = false,
}: {
  startupId: string;
  companyName?: string | null;
  onRulingRecorded?: () => void;
  readOnly?: boolean;
}) {
  const opportunity = useQuery({
    queryKey: ['institutional', 'opportunity', 'legacy', startupId],
    queryFn: () => fetchOpportunityByLegacyStartup(startupId),
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

  return (
    <MemoDecisionBrief brief={brief} stateMessage={stateMessage}>
      {hasClaims ? (
        <details className="memoDecisionDisclosure">
          <summary>Review supporting evidence</summary>
          <div className="memoDecisionDisclosureBody">
            <ClaimEvidenceLedger ledger={evidence.data!} readOnly={readOnly} />
          </div>
        </details>
      ) : null}

      {!rulings.isError ? <RulingHistory rulings={rulings.data ?? []} /> : null}

      {canCompose ? (
        <HumanRulingComposer
          opportunityId={opportunity.data!.opportunity_id}
          recommendationId={recommendationId}
          recommendedDecision={recommendedDecision}
          companyName={companyName}
          onRecorded={onRulingRecorded}
          readOnly={readOnly}
        />
      ) : null}
    </MemoDecisionBrief>
  );
}
