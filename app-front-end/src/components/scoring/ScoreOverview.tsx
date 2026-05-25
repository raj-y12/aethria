import type { ScoringPresentation, StructuredScoring } from '../../types/startup';
import { getScoreBand } from '../../design-system/semantics';

interface ScoreOverviewProps {
  scoring: StructuredScoring;
  presentation?: ScoringPresentation | null;
}

export default function ScoreOverview({ scoring, presentation }: ScoreOverviewProps) {
  const overallScore = presentation?.overall_score ?? scoring.overall_score;
  const overallBand = presentation?.overall_band ?? getScoreBand(scoring.overall_score).label;
  const evidenceLabel = presentation?.confidence_label ?? null;
  const evidenceTooltip = presentation?.confidence_tooltip ?? null;

  return (
    <div className="memoDocScoreOverview">
      <div className="memoDocOverallScoreRow">
        <div className="memoDocOverallScoreBlock">
          <p className="memoDocOverallScoreLabel">Overall score</p>
          <div className="memoDocOverallScoreMain">
            <p className="memoDocOverallScoreValue">
              {overallScore.toFixed(1)}
            </p>
            <p className="memoDocScorePanelMeta">/ 10</p>
            <p className="memoDocScoreBandTag">{overallBand}</p>
          </div>
          {evidenceLabel && (
            <p className="memoDocEvidenceConfidence" title={evidenceTooltip ?? undefined}>
              Evidence: {evidenceLabel}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
