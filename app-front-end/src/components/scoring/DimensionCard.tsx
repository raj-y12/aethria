import type { ScoringDimension } from '../../types/startup';
import { useState } from 'react';
import { getScoreBand } from '../../design-system/semantics';
import ConfidenceIndicator from './ConfidenceIndicator';
import ComponentBar from './ComponentBar';

interface DimensionCardProps {
  id: string;
  title: string;
  dimension: ScoringDimension;
}

const DIMENSION_WEIGHTS: Record<string, Record<string, number>> = {
  market: { tam: 0.3, growth_rate: 0.2, urgency: 0.15, timing: 0.15, competition: 0.2 },
  execution: { traction: 0.3, growth_velocity: 0.2, gtm_effectiveness: 0.2, team_execution: 0.15, operational_velocity: 0.15 },
  product: { value_prop: 0.25, pain_alignment: 0.25, differentiation: 0.2, ux: 0.15, retention: 0.15 },
  technical: { complexity: 0.25, engineering_quality: 0.2, scalability: 0.2, data_advantage: 0.2, architecture: 0.15 },
  defensibility: { network_effects: 0.25, switching_costs: 0.2, proprietary_data: 0.2, barriers: 0.2, brand: 0.15 },
};

const DIMENSION_KEY_BY_TITLE: Record<string, string> = {
  Market: 'market',
  Execution: 'execution',
  Product: 'product',
  Technical: 'technical',
  Defensibility: 'defensibility',
};

export default function DimensionCard({ id, title, dimension }: DimensionCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const entries = Object.entries(dimension.components ?? {});
  const band = getScoreBand(dimension.score).label;
  const dimKey = DIMENSION_KEY_BY_TITLE[title] ?? title.toLowerCase();
  const weights = DIMENSION_WEIGHTS[dimKey] ?? {};
  const confidenceLabel = typeof dimension.confidence === 'number' ? `${Math.round(dimension.confidence * 100)}%` : '—';

  return (
    <article id={id} className="memoDocDimensionCard">
      <div className="w-full pb-2">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-1.5">
              <p className="memoDocScorePanelTitle">{title}</p>
              <span className="memoDocScoreBandTag">{band}</span>
            </div>
            <div className="mt-1 flex items-end gap-2">
              <p className="memoDocScorePanelNumber">{dimension.score.toFixed(1)}</p>
              <p className="mb-0.5 memoDocScorePanelMeta">Confidence {confidenceLabel}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setIsExpanded((prev) => !prev)}
            className="memoDocTooltipBtn min-h-9 min-w-[84px] rounded-none px-2 py-1 transition-colors hover:text-oxford"
            aria-expanded={isExpanded}
            aria-controls={`${id}-components`}
          >
            {isExpanded ? 'Collapse' : 'Expand'}
          </button>
        </div>
        <ConfidenceIndicator confidence={dimension.confidence} />
      </div>
      <div id={`${id}-components`} className={`mt-1.5 ${isExpanded ? 'block' : 'hidden'}`} aria-hidden={!isExpanded}>
        {entries.map(([name, component]) => (
          <ComponentBar
            key={`${id}-${name}`}
            name={name}
            component={component}
            weight={weights[name] ?? 0}
          />
        ))}
      </div>
    </article>
  );
}
