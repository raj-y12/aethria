import type { ScoringPresentation, StructuredScoring } from '../../types/startup';
import { getScoreBand } from '../../design-system/semantics';
import { getEvidenceConfidenceLabel } from './ConfidenceIndicator';

interface ScoreOverviewProps {
  scoring: StructuredScoring;
  presentation?: ScoringPresentation | null;
}

export default function ScoreOverview({ scoring, presentation }: ScoreOverviewProps) {
  const overallScore = presentation?.overall_score ?? scoring.overall_score;
  const overallBand = presentation?.overall_band ?? getScoreBand(scoring.overall_score).label;
  const evidenceLabel =
    presentation?.confidence_label
    ?? getEvidenceConfidenceLabel(scoring.overall_confidence);
  const evidenceTooltip = presentation?.confidence_tooltip ?? undefined;
  const consistencyNote = presentation?.consistency_audit?.review_notes?.[0] ?? null;

  const line = [
    `${overallScore.toFixed(1)} / 10`,
    overallBand,
    evidenceLabel ? `${evidenceLabel} evidence` : null,
  ].filter(Boolean).join('   ·   ');

  return (
    <div className="memoScoreOverview">
      <p className="memoScoreOverviewLine" title={evidenceTooltip}>{line}</p>
      {consistencyNote && (
        <p className="memoScoreOverviewNote" role="note">{consistencyNote}</p>
      )}
    </div>
  );
}
