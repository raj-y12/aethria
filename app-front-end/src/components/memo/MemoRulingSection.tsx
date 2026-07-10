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
  const decisionLabel = {
    YES: 'Invest',
    MAYBE: 'Monitor',
    NO: 'Pass',
  };

  return (
    <section className="memoDocSection memoDecisionRecord" aria-labelledby="memo-decision-record">
      <div className="memoDecisionRuleTop" />

      <div className="memoDecisionContent">
        <h2 className="memoDecisionHeading" id="memo-decision-record">
          Decision Record
        </h2>

        {/* Decision choices — framed as prominent options */}
        <div className="memoDecisionChoicesFrame" role="group" aria-label="Record your ruling">
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
              className={`memoDecisionOption memoDecisionOption--${decision.toLowerCase()}${
                rulingDecision === decision ? ' memoDecisionOption--active' : ''
              }`}
            >
              <span className="memoDecisionLabel">{label}</span>
              <span className="memoDecisionCode" aria-hidden>{decision}</span>
            </button>
          ))}
        </div>

        {/* Rationale section */}
        <div className="memoDecisionSection">
          <label htmlFor="memo-rationale" className="memoDecisionSectionLabel">
            Rationale
          </label>
          <textarea
            id="memo-rationale"
            value={rulingNotes}
            onChange={(e) => onNotesChange(e.target.value)}
            disabled={rulingSaving}
            rows={3}
            className="memoDecisionTextarea"
            placeholder="Explain your reasoning (minimum 5 characters)"
            aria-label="Ruling rationale"
          />
        </div>

        {/* Risk acknowledgement — gated step */}
        {needsRiskAcknowledgement && !risksReviewed ? (
          <div className="memoDecisionSection memoDecisionRiskGate">
            <button
              type="button"
              onClick={onAcknowledgeRisks}
              className="memoRiskAckButton"
              disabled={rulingSaving}
              aria-label="Acknowledge that you have reviewed high-severity risks"
            >
              <span className="memoRiskAckCheckbox" />
              <span>I have reviewed high-severity risks</span>
            </button>
          </div>
        ) : null}

        {/* Submit */}
        <div className="memoDecisionSubmit">
          <button
            type="button"
            onClick={onSubmit}
            disabled={
              !rulingDecision || rulingNotes.trim().length < 5 || rulingSaving || riskReviewOutstanding
            }
            className="memoDecisionSubmitButton"
            title={riskReviewOutstanding ? 'Acknowledge risks to commit' : undefined}
          >
            {rulingSaving ? 'Recording…' : 'Commit ruling'}
          </button>
          {rulingError ? (
            <span className="memoDecisionError" role="alert">
              {rulingError}
            </span>
          ) : null}
        </div>
      </div>

      <div className="memoDecisionRuleBottom" />
    </section>
  );
}
