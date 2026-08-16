import type { HumanRuling, HumanRulingRecordDecision } from '../../api/decisions';
import { useMemoDecisionBrief } from '../../hooks/useMemoDecisionBrief';
import MemoDecisionBrief from '../memo/MemoDecisionBrief';
import ClaimEvidenceLedger from './ClaimEvidenceLedger';
import HumanRulingComposer from './HumanRulingComposer';

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
  const {
    opportunity,
    evidence,
    rulings,
    brief,
    stateMessage,
    recommendationId,
    recommendedDecision,
    hasClaims,
    canCompose,
    rulingsError,
  } = useMemoDecisionBrief(startupId);

  return (
    <MemoDecisionBrief brief={brief} stateMessage={stateMessage}>
      {hasClaims ? (
        <details className="memoDecisionDisclosure">
          <summary>Review supporting evidence</summary>
          <div className="memoDecisionDisclosureBody">
            <ClaimEvidenceLedger ledger={evidence!} readOnly={readOnly} />
          </div>
        </details>
      ) : null}

      {!rulingsError ? <RulingHistory rulings={rulings ?? []} /> : null}

      {canCompose ? (
        <HumanRulingComposer
          opportunityId={opportunity!.opportunity_id}
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
