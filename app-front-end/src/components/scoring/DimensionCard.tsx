import type { ScoringDimension } from '../../types/startup';
import { useState } from 'react';
import { getScoreBand } from '../../design-system/semantics';
import ConfidenceIndicator, { formatConfidencePercent } from './ConfidenceIndicator';
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

function prettyName(name: string): string {
  return name
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

export default function DimensionCard({ id, title, dimension }: DimensionCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const criteriaEntries = Object.entries(dimension.criteria ?? {});
  const entries = Object.entries(dimension.components ?? {});
  const hasCriteria = criteriaEntries.length > 0;
  const hasComponents = entries.length > 0;
  const reasoning = (dimension.reasoning ?? []).filter((s) => typeof s === 'string' && s.trim().length > 0);
  const weaknesses = (dimension.weaknesses ?? []).filter((s) => typeof s === 'string' && s.trim().length > 0);
  const scoreLabel = typeof dimension.score_label === 'string' && dimension.score_label.trim().length > 0
    ? dimension.score_label.trim()
    : null;
  const hasNarrative = reasoning.length > 0 || weaknesses.length > 0 || !!scoreLabel;
  const hasDetail = hasCriteria || hasComponents || hasNarrative;
  const band = getScoreBand(dimension.score).label;
  const dimKey = DIMENSION_KEY_BY_TITLE[title] ?? title.toLowerCase();
  const weights = DIMENSION_WEIGHTS[dimKey] ?? {};
  const confidenceLabel = formatConfidencePercent(dimension.confidence);
  const lowConfidence = typeof dimension.confidence === 'number' && dimension.confidence < 0.3;
  const scoreText = lowConfidence ? String(Math.round(dimension.score)) : dimension.score.toFixed(1);

  return (
    <article id={id} className="memoDocDimensionCard">
      <div className="memoDocDimensionHeader">
        <div className="memoDocDimensionTopline">
          <div className="memoDocDimensionTitleGroup">
            <div className="memoDocDimensionTitleRow">
              <p className="memoDocScorePanelTitle">{title}</p>
              <span className="memoDocScoreBandTag">{band}</span>
            </div>
            <div className="memoDocDimensionScoreRow">
              <p className="memoDocScorePanelNumber">{scoreText}</p>
              <p className="memoDocScorePanelMeta">Confidence {confidenceLabel}</p>
              {lowConfidence && <p className="memoDocScorePanelMeta">Low confidence · reduced precision</p>}
            </div>
          </div>
          {hasDetail && (
            <button
              type="button"
              onClick={() => setIsExpanded((prev) => !prev)}
              className="memoDocTooltipBtn memoDocDimensionDetailBtn"
              aria-expanded={isExpanded}
              aria-controls={`${id}-components`}
            >
              {isExpanded ? 'Hide detail' : 'Detail'}
            </button>
          )}
        </div>
        <ConfidenceIndicator confidence={dimension.confidence} />
      </div>
      {hasDetail && (
        <div
          id={`${id}-components`}
          className={isExpanded ? ((hasCriteria || hasComponents) ? 'memoDocComponentBars' : 'memoDocDimensionNarrative') : 'hidden'}
          aria-hidden={!isExpanded}
        >
          {hasCriteria
            ? criteriaEntries.map(([name, criterion]) => {
                const score = Math.max(0, Math.min(10, criterion.score));
                const pct = `${(score / 10) * 100}%`;
                const criterionLowConfidence = typeof criterion.confidence === 'number' && criterion.confidence < 0.3;
                return (
                  <div key={`${id}-${name}`} className="memoDocComponentBar">
                    <div className="memoDocComponentBarInner">
                      <div className="memoDocComponentBarHeader">
                        <p className="memoDocDimName">{criterion.name || prettyName(name)}</p>
                        <p className="memoDocScorePanelMeta">
                          <span>{criterionLowConfidence ? Math.round(score) : score.toFixed(1)}</span> · w {Math.round(criterion.weight)}%
                        </p>
                      </div>
                      <div className="memoDocComponentTrack">
                        <div className="memoDocComponentFill" style={{ width: pct }} />
                      </div>
                      <div className="memoDocComponentDetail">
                        <p className="memoDocExpandedLabel">
                          {criterion.missing_data_applied ? 'Missing evidence applied' : `Evidence: ${criterion.evidence_status}`}
                        </p>
                        <p className="memoDocDimText">{criterion.reasoning}</p>
                        {criterion.source_components?.length > 0 && (
                          <p className="memoDocScorePanelMeta">Signals: {criterion.source_components.join(', ')}</p>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })
            : hasComponents
            ? entries.map(([name, component]) => (
                <ComponentBar
                  key={`${id}-${name}`}
                  name={name}
                  component={component}
                  weight={weights[name] ?? 0}
                />
              ))
            : (
              <>
                {scoreLabel && (
                  <p className="memoDocDimensionNarrativeLabel">{scoreLabel}</p>
                )}
                {reasoning.length > 0 && (
                  <div className="memoDocDimensionNarrativeBlock">
                    <p className="memoDocDimensionNarrativeHead">Reasoning</p>
                    <ul className="memoDocDimensionNarrativeList">
                      {reasoning.map((item, i) => (
                        <li key={`${id}-r-${i}`} className="memoDocDimensionNarrativeItem">
                          <span className="memoDocDimensionNarrativeBullet" aria-hidden>·</span>
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {weaknesses.length > 0 && (
                  <div className="memoDocDimensionNarrativeBlock">
                    <p className="memoDocDimensionNarrativeHead">Weaknesses</p>
                    <ul className="memoDocDimensionNarrativeList">
                      {weaknesses.map((item, i) => (
                        <li key={`${id}-w-${i}`} className="memoDocDimensionNarrativeItem">
                          <span className="memoDocDimensionNarrativeBullet" aria-hidden>·</span>
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
        </div>
      )}
    </article>
  );
}
