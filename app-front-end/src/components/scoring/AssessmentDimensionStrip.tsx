import { useEffect, useState } from 'react';
import type { ScoringDimensionKey, ScoringPresentation, StructuredScoring } from '../../types/startup';
import { getEvidenceConfidenceLabel, isLowEvidence } from './ConfidenceIndicator';
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
// Confidence is signalled separately (class + tooltip), using the SAME low-evidence
// threshold and vocabulary as the rest of the app (isLowEvidence / evidence label).

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
          // An unscored dimension has no evidence — show "Not scored", never the
          // numeric placeholder (audit C2 / Layer 3).
          const unscored = !presDim && dimension.unscored === true;
          const scoreText = unscored
            ? 'Not scored'
            : presDim
              ? presDim.score.toFixed(1)
              : dimension.score.toFixed(1);
          const lowConfidence = !presDim && !unscored && isLowEvidence(dimension.confidence);
          const narrative = unscored
            ? 'No supporting evidence — excluded from the overall.'
            : dimensionBriefTake(dimension, presDim);
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
                    className={`memoScoreBriefScore${lowConfidence ? ' memoScoreBriefScore--lowConfidence' : ''}${unscored ? ' memoScoreBriefScore--unscored' : ''}`}
                    title={
                      unscored
                        ? 'No supporting evidence for this dimension'
                        : lowConfidence
                          ? `${getEvidenceConfidenceLabel(dimension.confidence)} evidence`
                          : undefined
                    }
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
