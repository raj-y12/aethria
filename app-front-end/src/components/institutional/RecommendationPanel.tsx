import type { EvaluationRecord } from '../../api/evaluations';

function text(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null;
}

export default function RecommendationPanel({ evaluation }: { evaluation: EvaluationRecord | null }) {
  if (!evaluation?.recommendation) {
    return <p className="type-body text-oxford/55">No completed immutable evaluation is available.</p>;
  }
  const evaluationData = evaluation.evaluation;
  const recommendation = evaluation.recommendation;
  const modelId = text(evaluationData.model_manifest.model_id);
  const promptVersion = text(evaluationData.prompt_manifest.prompt_version);
  const dependencies = [
    ['Model', modelId],
    ['Prompt', promptVersion],
    ['Policy', text(evaluationData.policy_version_id)],
    ['Policy hash', text(evaluationData.policy_hash)],
    ['Rubric', text(evaluationData.rubric_version)],
    ['Rules', text(evaluationData.partner_rules_version)],
    ['Rules hash', text(evaluationData.partner_rules_hash)],
  ].filter((item): item is [string, string] => Boolean(item[1]));
  return (
    <section aria-label="Current recommendation" className="border-y border-oxford/10 py-phi-4">
      <div className="flex items-baseline justify-between gap-phi-4">
        <p className="type-label-section">Current recommendation</p>
        <span className="type-status">{recommendation.recommended_state.replace(/_/g, ' ')}</span>
      </div>
      <div className="mt-phi-3 grid gap-phi-4 sm:grid-cols-2">
        <div>
          <p className="type-meta text-oxford/45">Decision drivers</p>
          {recommendation.decision_drivers.length ? (
            <ul className="mt-phi-2 space-y-1">{recommendation.decision_drivers.map((item) => <li key={item} className="type-body text-oxford/70">{item}</li>)}</ul>
          ) : <p className="type-body mt-phi-2 text-oxford/55">No decision driver was recorded.</p>}
        </div>
        <div>
          <p className="type-meta text-oxford/45">Principal risks</p>
          {recommendation.principal_risks.length ? (
            <ul className="mt-phi-2 space-y-1">{recommendation.principal_risks.map((item) => <li key={item} className="type-body text-oxford/70">{item}</li>)}</ul>
          ) : <p className="type-body mt-phi-2 text-oxford/55">No principal risk was recorded.</p>}
        </div>
      </div>
      <p className="type-meta mt-phi-3 text-oxford/50">
        Confidence {Math.round(recommendation.confidence * 100)}% · attention priority {recommendation.attention_priority}
        {recommendation.human_review_required ? ' · human review required' : ''}
      </p>
      <details className="mt-phi-4 border-t border-oxford/10 pt-phi-3">
        <summary className="type-action cursor-pointer">Evaluation dependencies</summary>
        <dl className="mt-phi-3 grid gap-x-phi-5 gap-y-phi-2 sm:grid-cols-2">
          {dependencies.map(([label, value]) => (
            <div key={label}><dt className="type-meta text-oxford/45">{label}</dt><dd className="type-body mt-1 break-all text-oxford/70">{value}</dd></div>
          ))}
          {dependencies.length === 0 ? <p className="type-body text-oxford/55">Version metadata was not exposed in this evaluation.</p> : null}
        </dl>
      </details>
    </section>
  );
}
