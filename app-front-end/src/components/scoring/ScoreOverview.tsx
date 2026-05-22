import type { StructuredScoring } from '../../types/startup';
import { getScoreBand, SCORE_BANDS } from '../../design-system/semantics';

interface ScoreOverviewProps {
  scoring: StructuredScoring;
}

export default function ScoreOverview({ scoring }: ScoreOverviewProps) {
  const overallBand = getScoreBand(scoring.overall_score).label;
  const confidence = typeof scoring.overall_confidence === 'number' ? scoring.overall_confidence : null;
  const lowConfidence = confidence != null && confidence < 0.3;
  const scoreText = lowConfidence ? String(Math.round(scoring.overall_score)) : scoring.overall_score.toFixed(1);

  return (
    <div className="memoDocScoreOverview">
      <div className="memoDocOverallScoreRow">
        <div className="memoDocOverallScoreBlock">
          <p className="memoDocOverallScoreLabel">Overall score</p>
          <div className="memoDocOverallScoreMain">
            <p className="memoDocOverallScoreValue">
              {scoreText}
            </p>
            <p className="memoDocScorePanelMeta">/ 10</p>
            <p className="memoDocScoreBandTag">{overallBand}</p>
          </div>
          <p className="memoDocScoreScale">
            {SCORE_BANDS.map((band) => (
              <span key={band.label}>
                {band.range[0]}-{band.range[1]} {band.label}
              </span>
            ))}
          </p>
          {scoring.policy_version_id && (
            <p className="memoDocScorePanelMeta">Policy version {scoring.policy_version_id}</p>
          )}
        </div>
      </div>
    </div>
  );
}
