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
      <details className="memoScoreMethod">
        <summary className="memoScoreMethodSummary">How this was scored</summary>
        <div className="memoScoreMethodBody">
          <p>
            Each dimension is scored 1–10 from extracted evidence — bands:
            1–3 Weak · 4–5 Concerning · 6–7 Promising · 8–10 Strong.
          </p>
          <p>
            Overall = mean of Market, Product, Technical, Execution. Defensibility is a
            separate moat signal and is not averaged in.
          </p>
          <p>
            A dimension with no supporting evidence is shown as “Not scored” and excluded
            from the overall — it is never counted as an average score. “Evidence” labels
            (Limited → Extensive) describe how well-supported a score is, separately from
            the score itself.
          </p>
        </div>
      </details>
      {consistencyNote && (
        <p className="memoScoreOverviewNote" role="note">{consistencyNote}</p>
      )}
    </div>
  );
}
