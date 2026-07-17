import { useQuery } from '@tanstack/react-query';
import { fetchOpportunityByLegacyStartup } from '../../api/identity';
import { fetchEvidenceLedger } from '../../api/evidence';
import { fetchCurrentEvaluation } from '../../api/evaluations';
import {
  listHumanRulings,
  type HumanRuling,
  type HumanRulingDecision,
} from '../../api/decisions';
import ClaimEvidenceLedger from './ClaimEvidenceLedger';
import HumanRulingComposer from './HumanRulingComposer';
import RecommendationPanel from './RecommendationPanel';

function nestedString(value: unknown, key: string): string | null {
  if (!value || typeof value !== 'object') return null;
  const candidate = (value as Record<string, unknown>)[key];
  return typeof candidate === 'string' ? candidate : null;
}

function decisionLabel(decision: HumanRulingDecision): string {
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
      <p className="memoDecisionMeta">
        {rulingDate(latest.created_at) ?? 'Recorded'}
        {typeof latest.investor_confidence === 'number'
          ? ` · ${Math.round(latest.investor_confidence * 100)}% confidence`
          : ''}
      </p>
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

function RulingState({ message, unavailable = false }: { message: string; unavailable?: boolean }) {
  return (
    <section
      className="memoDocSection memoRulingControls memoDecisionWorkspace"
      aria-label={unavailable ? 'Your ruling unavailable' : 'Your ruling'}
    >
      <h2 className="memoDocSectionHead">Your ruling</h2>
      <p className="memoDecisionIntro">{message}</p>
    </section>
  );
}

export default function OpportunityIntelligence({
  startupId,
  readOnly = false,
}: {
  startupId: string;
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
  const recommendationState: string | undefined = evaluation.data?.recommendation?.recommended_state;
  const recommendedDecision: HumanRulingDecision | null =
    recommendationState === 'invest'
      || recommendationState === 'monitor'
      || recommendationState === 'pass'
      || recommendationState === 'advance'
      ? recommendationState
      : null;

  // A recommendation only earns the panel when it actually gives reasons —
  // insufficient-evidence husks (0% confidence, no drivers, no risks) stay hidden.
  const recommendation = evaluation.data?.recommendation;
  const hasRecommendation = Boolean(
    recommendation && (recommendation.decision_drivers.length > 0 || recommendation.principal_risks.length > 0),
  );
  const hasClaims = Boolean(evidence.data?.claims.some((claim) => claim.status === 'current'));

  if (opportunity.isLoading) {
    return <RulingState message="Preparing the recommendation and decision record…" />;
  }
  if (opportunity.isError || !opportunity.data) {
    return (
      <RulingState
        unavailable
        message="This memo is still being connected to its decision record. The ruling controls will appear when that link is complete."
      />
    );
  }

  return (
    <section className="memoDocSection memoRulingControls memoDecisionWorkspace" aria-labelledby="opportunity-final-ruling">
      <h2 className="memoDocSectionHead" id="opportunity-final-ruling">Your ruling</h2>
      <p className="memoDecisionIntro">
        {hasRecommendation
          ? 'See why Aethria leans this way, review the evidence that matters, then make the call for your fund.'
          : 'The memo above is the case. Record the call for your fund.'}
      </p>

      {/* The reasoning and claim ledger appear only once the institutional pipeline
          actually produces them; an always-empty panel is noise, not transparency. */}
      {hasRecommendation ? <RecommendationPanel evaluation={evaluation.data ?? null} /> : null}

      {hasClaims ? (
        <details className="memoDecisionDisclosure">
          <summary>Review supporting evidence</summary>
          <div className="memoDecisionDisclosureBody">
            <ClaimEvidenceLedger ledger={evidence.data!} readOnly={readOnly} />
          </div>
        </details>
      ) : null}

      {rulings.isError ? (
        <p role="alert" className="memoDecisionMuted">Earlier rulings could not be loaded.</p>
      ) : <RulingHistory rulings={rulings.data ?? []} />}

      <HumanRulingComposer
        opportunityId={opportunity.data.opportunity_id}
        recommendationId={recommendationId}
        recommendedDecision={recommendedDecision}
        readOnly={readOnly}
      />
    </section>
  );
}
