import type { EvaluationRecord } from '../../api/evaluations';

function ReasonList({ items, empty }: { items: string[]; empty: string }) {
  if (items.length === 0) return <p className="memoDecisionMuted">{empty}</p>;
  return (
    <ul className="memoDecisionReasonList">
      {items.map((item) => <li key={item}>{item}</li>)}
    </ul>
  );
}

export default function RecommendationPanel({ evaluation }: { evaluation: EvaluationRecord | null }) {
  if (!evaluation?.recommendation) {
    return (
      <section className="memoDecisionReasoning" aria-label="Aethria reasoning">
        <p className="memoDecisionEyebrow">Why Aethria leans this way</p>
        <p className="memoDecisionMuted">The recommendation is still being assembled.</p>
      </section>
    );
  }

  const recommendation = evaluation.recommendation;
  return (
    <section className="memoDecisionReasoning" aria-label="Aethria reasoning">
      <div className="memoDecisionReasoningHead">
        <p className="memoDecisionEyebrow">Why Aethria leans this way</p>
        <p className="memoDecisionMeta">{Math.round(recommendation.confidence * 100)}% confidence</p>
      </div>
      <div className="memoDecisionReasoningGrid">
        <div>
          <h3>What supports the case</h3>
          <ReasonList items={recommendation.decision_drivers} empty="No decisive supporting reason was recorded." />
        </div>
        <div>
          <h3>What holds it back</h3>
          <ReasonList items={recommendation.principal_risks} empty="No principal risk was recorded." />
        </div>
      </div>
      {recommendation.change_conditions.length > 0 ? (
        <p className="memoDecisionChangeCondition">
          <span>What would change the view</span>
          {recommendation.change_conditions.join(' ')}
        </p>
      ) : null}
    </section>
  );
}
