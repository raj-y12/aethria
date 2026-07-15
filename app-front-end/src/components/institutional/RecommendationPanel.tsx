import type { EvaluationRecord } from '../../api/evaluations';

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? value as Record<string, unknown> : {};
}

function text(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null;
}

export default function RecommendationPanel({ evaluation }: { evaluation: EvaluationRecord | null }) {
  if (!evaluation) {
    return <p className="type-body text-oxford/55">No completed immutable evaluation is available.</p>;
  }
  const evaluationData = record(evaluation.evaluation ?? evaluation);
  const recommendation = record(evaluation.recommendation);
  const dependencies = [
    ['Model', text(evaluationData.model_id ?? evaluationData.model)],
    ['Prompt', text(evaluationData.prompt_version)],
    ['Policy', text(evaluationData.policy_version_id ?? evaluationData.policy_version)],
    ['Rubric', text(evaluationData.rubric_version)],
    ['Rules', text(evaluationData.rules_version)],
  ].filter((item): item is [string, string] => Boolean(item[1]));
  return (
    <section aria-label="Current recommendation" className="border-y border-oxford/10 py-phi-4">
      <div className="flex items-baseline justify-between gap-phi-4">
        <p className="type-label-section">Current recommendation</p>
        <span className="type-status">{text(recommendation.decision ?? recommendation.recommendation)?.replace(/_/g, ' ') || 'Unavailable'}</span>
      </div>
      <p className="type-body mt-phi-3 text-oxford/70">
        {text(recommendation.rationale ?? recommendation.decision_rationale) || 'No recommendation rationale was recorded.'}
      </p>
      {typeof recommendation.confidence === 'number' ? (
        <p className="type-meta mt-phi-2 text-oxford/50">Confidence {Math.round(recommendation.confidence * 100)}%</p>
      ) : null}
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

