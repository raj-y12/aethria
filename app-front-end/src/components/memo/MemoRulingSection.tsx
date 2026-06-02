import type { RulingDecision } from '../../types/startup';

type Props = {
  rulingDecision: RulingDecision | null;
  rulingNotes: string;
  rulingSaving: boolean;
  rulingError: string | null;
  needsRiskAcknowledgement: boolean;
  risksReviewed: boolean;
  riskReviewOutstanding: boolean;
  onSelectDecision: (decision: RulingDecision) => void;
  onNotesChange: (value: string) => void;
  onAcknowledgeRisks: () => void;
  onSubmit: () => void;
};

export default function MemoRulingSection({
  rulingDecision,
  rulingNotes,
  rulingSaving,
  rulingError,
  needsRiskAcknowledgement,
  risksReviewed,
  riskReviewOutstanding,
  onSelectDecision,
  onNotesChange,
  onAcknowledgeRisks,
  onSubmit,
}: Props) {
  return (
    <section className="memoDocSection memoRulingControls" aria-labelledby="memo-final-ruling">
      <h2 className="memoDocSectionHead" id="memo-final-ruling">
        Your ruling
      </h2>
      <div className="memoRulingPanel">
        <div className="memoDecisionChoices" role="group" aria-label="Choose final ruling">
          {(
            [
              ['YES', 'Invest'],
              ['MAYBE', 'Monitor'],
              ['NO', 'Pass'],
            ] as const
          ).map(([decision, label]) => (
            <button
              key={decision}
              type="button"
              onClick={() => onSelectDecision(decision)}
              aria-pressed={rulingDecision === decision}
              disabled={rulingSaving}
              className="memoDecisionChoice"
            >
              {label}
            </button>
          ))}
        </div>
        <textarea
          value={rulingNotes}
          onChange={(e) => onNotesChange(e.target.value)}
          disabled={rulingSaving}
          rows={2}
          className="memoRulingTextarea"
          placeholder="Rationale"
          aria-label="Ruling rationale"
        />
        {needsRiskAcknowledgement && !risksReviewed ? (
          <button
            type="button"
            onClick={onAcknowledgeRisks}
            className="memoRiskAckButton"
            disabled={rulingSaving}
          >
            Acknowledge high-severity risks
          </button>
        ) : null}
        <div className="memoRulingSubmitRow">
          <button
            type="button"
            onClick={onSubmit}
            disabled={
              !rulingDecision || rulingNotes.trim().length < 5 || rulingSaving || riskReviewOutstanding
            }
            className="memoRulingSubmit"
            title={riskReviewOutstanding ? 'Acknowledge risks to commit' : undefined}
          >
            {rulingSaving ? 'Recording…' : 'Commit ruling'}
          </button>
          {rulingError ? <span className="memoRulingError">{rulingError}</span> : null}
        </div>
      </div>
    </section>
  );
}
