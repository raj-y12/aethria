import { useEffect, useState } from 'react';
import type { ScoringDimensionKey, ScoringPresentation, StructuredScoring } from '../../types/startup';
import { normalizeConfidence } from './ConfidenceIndicator';
import DimensionCard from './DimensionCard';
import { dimensionBriefTake } from '../../lib/scoringRationale';

export type AssessmentDimensionDef = {
  key: ScoringDimensionKey;
  label: string;
  id: string;
};

interface AssessmentDimensionStripProps {
  dimensions: AssessmentDimensionDef[];
  scoring: StructuredScoring;
  presentation?: ScoringPresentation | null;
  contentKey: string;
}

// The displayed score must never change with confidence — a low-confidence 7.5
// previously rendered as "8", reading as a different, lower score (audit B5).
// Confidence is now signalled separately (class + tooltip), not by mutating the digit.
function isLowConfidence(confidence: number | null | undefined): boolean {
  const normalized = normalizeConfidence(confidence);
  return normalized != null && normalized < 0.4;
}

export default function AssessmentDimensionStrip({
  dimensions,
  scoring,
  presentation,
  contentKey,
}: AssessmentDimensionStripProps) {
  const [activeKey, setActiveKey] = useState<ScoringDimensionKey>(dimensions[0]?.key ?? 'market');

  useEffect(() => {
    setActiveKey(dimensions[0]?.key ?? 'market');
  }, [contentKey, dimensions]);

  const activeDef = dimensions.find((d) => d.key === activeKey) ?? dimensions[0];
  if (!activeDef) return null;

  const activePresentationDim = presentation?.dimensions?.find((d) => d.id === activeKey) ?? null;

  return (
    <div className="memoAssessmentDimensionStrip">
      <ul className="memoScoreBriefList" role="tablist" aria-label="Assessment dimensions">
        {dimensions.map((dim) => {
          const dimension = scoring[dim.key];
          const presDim = presentation?.dimensions?.find((d) => d.id === dim.key);
          const selected = activeKey === dim.key;
          const scoreText = presDim ? presDim.score.toFixed(1) : dimension.score.toFixed(1);
          const lowConfidence = !presDim && isLowConfidence(dimension.confidence);
          const narrative = dimensionBriefTake(dimension, presDim);
          return (
            <li key={dim.key}>
              <button
                type="button"
                role="tab"
                id={`${contentKey}-dim-tab-${dim.key}`}
                aria-selected={selected}
                aria-controls={`${dim.id}-detail`}
                className={`memoScoreBriefRow${selected ? ' memoScoreBriefRow--active' : ''}`}
                onClick={() => setActiveKey(dim.key)}
              >
                <span className="memoScoreBriefRowTop">
                  <span className="memoScoreBriefName">{dim.label}</span>
                  <span
                    className={`memoScoreBriefScore${lowConfidence ? ' memoScoreBriefScore--lowConfidence' : ''}`}
                    title={lowConfidence ? 'Low evidence confidence' : undefined}
                  >
                    {scoreText}
                  </span>
                </span>
                <span className="memoScoreBriefNarrative">{narrative}</span>
              </button>
            </li>
          );
        })}
      </ul>
      <DimensionCard
        key={`${contentKey}-${activeDef.key}`}
        variant="detail"
        id={`${activeDef.id}-detail`}
        title={activeDef.label}
        dimension={scoring[activeDef.key]}
        presentation={activePresentationDim}
        tabId={`${contentKey}-dim-tab-${activeDef.key}`}
      />
    </div>
  );
}
