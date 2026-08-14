import type { ScoringComponent } from '../../types/startup';

interface ComponentDetailProps {
  componentName: string;
  component: ScoringComponent;
  showDebug?: boolean;
}

export default function ComponentDetail({ componentName, component, showDebug = false }: ComponentDetailProps) {
  const deterministicMapping = component.label
    ? `Rule mapping: label "${component.label}" -> normalized score ${component.score.toFixed(1)}`
    : component.value != null && component.value !== ''
      ? `Value normalization: "${String(component.value)}" -> normalized score ${component.score.toFixed(1)}`
      : `Missing input fallback -> normalized score ${component.score.toFixed(1)}`;

  return (
    <div className="mt-2 border border-oxford/10 bg-paper px-3 py-2">
      <p className="type-label-section">{componentName}</p>
      <p className="mt-1.5 type-meta text-oxford/[0.62]">{deterministicMapping}</p>
      {component.rule && <p className="mt-1 type-meta text-oxford/65">Rule trigger: {component.rule}</p>}
      {component.evidence && <p className="mt-1.5 type-note text-oxford/75 leading-relaxed"><span className="text-oxford/[0.62]">Evidence:</span> {component.evidence}</p>}
      {component.value != null && component.value !== '' && (
        <p className="mt-1.5 type-meta text-oxford/65">Raw value: {component.value}</p>
      )}
      {component.label && <p className="mt-1 type-meta text-oxford/65">Label: {component.label}</p>}
      <p className="mt-1 type-meta text-oxford/65">Score rationale: {component.score.toFixed(1)} / 10</p>
      <p className="mt-1.5 type-note text-oxford/[0.72] leading-relaxed">{component.reasoning}</p>
      {showDebug && (
        <p className="mt-1.5 type-meta text-oxford/65">
          Confidence: {typeof component.confidence === 'number' ? component.confidence.toFixed(2) : 'n/a'}
        </p>
      )}
    </div>
  );
}
