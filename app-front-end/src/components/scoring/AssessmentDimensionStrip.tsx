import { useEffect, useState } from 'react';
import type { ScoringDimensionKey, ScoringPresentation, StructuredScoring } from '../../types/startup';
import { normalizeConfidence } from './ConfidenceIndicator';
import DimensionCard from './DimensionCard';

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

function dimensionScoreLabel(score: number, confidence: number | null | undefined): string {
  const lowConfidence = confidence != null && normalizeConfidence(confidence) != null && normalizeConfidence(confidence)! < 0.4;
  return lowConfidence ? String(Math.round(score)) : score.toFixed(1);
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
      <div className="memoDocScorecardRow" role="tablist" aria-label="Assessment dimensions">
        {dimensions.map((dim) => {
          const dimension = scoring[dim.key];
          const presDim = presentation?.dimensions?.find((d) => d.id === dim.key);
          const selected = activeKey === dim.key;
          const scoreText = presDim
            ? presDim.score.toFixed(1)
            : dimensionScoreLabel(dimension.score, dimension.confidence);
          return (
            <button
              key={dim.key}
              type="button"
              role="tab"
              id={`${contentKey}-dim-tab-${dim.key}`}
              aria-selected={selected}
              aria-controls={`${dim.id}-detail`}
              className="memoDocScoreBtn"
              onClick={() => setActiveKey(dim.key)}
            >
              <span className="memoDocScoreDim">{dim.label}</span>
              <span className="memoDocScoreVal">{scoreText}</span>
              {selected ? (
                <div className="memoDocScoreUnderline" aria-hidden />
              ) : (
                <div className="memoDocScoreColSpacer" aria-hidden />
              )}
            </button>
          );
        })}
      </div>
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
