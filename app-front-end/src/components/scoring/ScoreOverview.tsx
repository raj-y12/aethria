import type { StructuredScoring } from '../../types/startup';
import { getScoreBand, SCORE_BANDS } from '../../design-system/semantics';

interface ScoreOverviewProps {
  scoring: StructuredScoring;
}

export default function ScoreOverview({ scoring }: ScoreOverviewProps) {
  const overallBand = getScoreBand(scoring.overall_score).label;

  return (
    <div className="memoDocScoreOverview">
      <div className="memoDocOverallScoreRow">
        <div className="memoDocOverallScoreBlock">
          <p className="memoDocOverallScoreLabel">Overall score</p>
          <div className="memoDocOverallScoreMain">
            <p className="memoDocOverallScoreValue">
              {scoring.overall_score.toFixed(1)}
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
        </div>
      </div>
    </div>
  );
}
