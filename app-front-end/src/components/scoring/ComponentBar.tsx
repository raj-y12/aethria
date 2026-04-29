import type { ScoringComponent } from '../../types/startup';
import { useMemo } from 'react';

interface ComponentBarProps {
  name: string;
  component: ScoringComponent;
  weight?: number;
}

function prettyName(name: string): string {
  return name
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

export default function ComponentBar({ name, component, weight = 0 }: ComponentBarProps) {
  const score = Math.max(0, Math.min(10, component.score));
  const pct = `${(score / 10) * 100}%`;

  const detailSnippet = useMemo(() => {
    const reasoning = component.reasoning?.trim();
    if (reasoning) return reasoning;
    const evidence = component.evidence?.trim();
    if (evidence) return evidence;
    return 'No detailed reasoning provided.';
  }, [component.reasoning, component.evidence]);

  return (
    <div className="border-t border-oxford/8 py-2.5 first:border-t-0">
      <div className="w-full text-left">
        <div className="flex items-center justify-between gap-3">
          <p className="memoDocDimName">{prettyName(name)}</p>
          <p className="memoDocScorePanelMeta">
            <span className="font-mono">{score.toFixed(1)}</span> · w {Math.round(weight * 100)}%
          </p>
        </div>
        <div className="relative mt-1.5 h-[1px] w-full overflow-hidden bg-oxford/10">
          <div className="absolute inset-0 h-full origin-left bg-oxford/40" style={{ width: pct }} />
        </div>
        <div className="mt-2 space-y-1.5">
          <p className="memoDocExpandedLabel">
            {component.label ? `Label: ${component.label}` : component.value != null && component.value !== '' ? `Value: ${String(component.value)}` : 'Value: n/a'}
          </p>
          <p className="memoDocDimText break-words">
            {detailSnippet}
          </p>
        </div>
      </div>
    </div>
  );
}
