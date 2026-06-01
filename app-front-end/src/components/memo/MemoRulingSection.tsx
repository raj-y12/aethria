import type { ReactNode } from 'react';
import type { RulingDecision } from '../../types/startup';

type Props = {
  rulingIntro: string;
  nextStepItems: string[];
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
  renderWithMonoNumbers: (value: unknown) => ReactNode;
  normalizeListItemText: (value: unknown) => string;
};

export default function MemoRulingSection({
  rulingIntro,
  nextStepItems,
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
  renderWithMonoNumbers,
  normalizeListItemText,
}: Props) {
  return (
    <section className="memoDocSection memoRulingControls" aria-labelledby="memo-final-ruling">
      <h2 className="memoDocSectionHead" id="memo-final-ruling">
        Your Ruling
      </h2>
      <p className="memoRulingIntro">{rulingIntro}</p>
      {nextStepItems.length > 1 && (
        <ul className="memoList memoRulingSteps">
          {nextStepItems.map((item, idx) => (
            <li key={idx} className="memoListItem">
              <span className="memoBullet">
                <span className="memoNum">{idx + 1}</span>
              </span>
              <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
            </li>
          ))}
        </ul>
      )}
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
          placeholder="Ruling rationale..."
          aria-label="Final ruling rationale"
        />
        {needsRiskAcknowledgement && (
          <div
            className={`memoRiskGate${risksReviewed ? ' memoRiskGate--complete' : ''}`}
            aria-live="polite"
          >
            <div className="memoRiskGateCopy">
              <span className="memoRiskGateKicker">
                {risksReviewed ? 'Risk review confirmed' : 'Risk review required'}
              </span>
              <p className="memoRiskGateText">
                {risksReviewed
                  ? 'High-severity risks have been acknowledged. You can commit the ruling when ready.'
                  : 'High-severity risks are present. Confirm that you have reviewed them before committing a final ruling.'}
              </p>
            </div>
            <button
              type="button"
              onClick={onAcknowledgeRisks}
              className="memoRiskAckButton"
              aria-pressed={risksReviewed}
              disabled={rulingSaving || risksReviewed}
            >
              {risksReviewed ? 'Risk review acknowledged' : 'I have reviewed the high-severity risks'}
            </button>
          </div>
        )}
        <div className={`memoRulingSubmitRow${riskReviewOutstanding ? ' memoRulingSubmitRow--locked' : ''}`}>
          {riskReviewOutstanding && (
            <span className="memoRulingGateLabel">Final commit remains locked</span>
          )}
          <button
            type="button"
            onClick={onSubmit}
            disabled={
              !rulingDecision || rulingNotes.trim().length < 5 || rulingSaving || riskReviewOutstanding
            }
            className="memoRulingSubmit"
          >
            {rulingSaving ? 'Recording...' : 'Commit ruling'}
          </button>
          {riskReviewOutstanding && (
            <span className="memoRulingHint">Acknowledge the risk review to unlock this action.</span>
          )}
          {rulingError && <span className="memoRulingError">{rulingError}</span>}
        </div>
      </div>
    </section>
  );
}
