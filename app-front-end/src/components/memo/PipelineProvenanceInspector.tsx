import { buildPipelineProvenance } from '../../lib/pipelineProvenance';

export default function PipelineProvenanceInspector(
  props: Parameters<typeof buildPipelineProvenance>[0],
) {
  if (!import.meta.env.DEV) return null;
  return (
    <details className="border-y border-hairline py-phi-4 text-oxford print:hidden">
      <summary className="type-label-section cursor-pointer">Development provenance</summary>
      <p className="type-body-sm py-phi-3">
        Current API projections and their sources. Null means unavailable; matching values do not prove shared lineage.
      </p>
      <pre className="type-meta overflow-auto whitespace-pre-wrap break-words">
        {JSON.stringify(buildPipelineProvenance(props), null, 2)}
      </pre>
    </details>
  );
}
