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
    <div className="memoDocComponentBar">
      <div className="memoDocComponentBarInner">
        <div className="memoDocComponentBarHeader">
          <p className="memoDocDimName">{prettyName(name)}</p>
          <p className="memoDocScorePanelMeta">
            <span>{score.toFixed(1)}</span> · w {Math.round(weight * 100)}%
          </p>
        </div>
        <div className="memoDocComponentTrack">
          <div className="memoDocComponentFill" style={{ width: pct }} />
        </div>
        <div className="memoDocComponentDetail">
          <p className="memoDocExpandedLabel">
            {component.label ? `Label: ${component.label}` : component.value != null && component.value !== '' ? `Value: ${String(component.value)}` : 'Value: n/a'}
          </p>
          <p className="memoDocDimText">
            {detailSnippet}
          </p>
        </div>
      </div>
    </div>
  );
}
