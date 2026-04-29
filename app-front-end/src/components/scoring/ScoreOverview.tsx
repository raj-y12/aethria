import type { StructuredScoring } from '../../types/startup';
import { getScoreBand, SCORE_BANDS } from '../../design-system/semantics';

interface ScoreOverviewProps {
  scoring: StructuredScoring;
}

export default function ScoreOverview({ scoring }: ScoreOverviewProps) {
  const overallBand = getScoreBand(scoring.overall_score).label;

  return (
    <div className="memoDocScoreOverview">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div className="min-w-[140px]">
          <p className="memoDocOverallScoreLabel">Overall score</p>
          <div className="mt-1 flex items-end gap-1.5">
            <p className="memoDocOverallScoreValue">
              {scoring.overall_score.toFixed(1)}
            </p>
            <p className="mb-0.5 memoDocScorePanelMeta">/ 10</p>
            <p className="mb-0.5 memoDocScoreBandTag">{overallBand}</p>
          </div>
          <p className="memoDocScoreScale mt-1">
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
