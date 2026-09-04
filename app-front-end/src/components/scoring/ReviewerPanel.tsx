import type { ReactNode } from 'react';

// The prompted posture behind each row's name (audit 2026-08-15/17: "name each
// prompt posture" — same model, same evidence packet, differ only by instruction).
const REVIEWER_POSTURES: Record<string, string> = {
  DefaultReviewer: 'Balanced read of the same evidence packet.',
  SkepticalReviewer: 'Instructed to assume the worst on missing data and weight risk higher.',
  OpportunistReviewer: 'Instructed to give benefit of the doubt on early-stage gaps and weight upside higher.',
};

export type ScorecardReviewerRow = {
  key: string;
  name: string;
  score: number | null;
  verdict?: string;
  take?: string;
  /** Fraction of rubric sub-criteria with any extractable signal — not verified
   *  evidence or source coverage. Rendered as "N% data coverage", never "evidenced". */
  coverage?: number | null;
};

export type ScorecardReviewerConsensus = {
  min: number | null;
  max: number | null;
  spread: number | null;
  split: boolean;
  verdict?: string | null;
};

export interface ReviewerPanelProps {
  rows: ScorecardReviewerRow[];
  consensus: ScorecardReviewerConsensus;
  renderNumbers?: (value: unknown) => ReactNode;
}

function identity(value: unknown): ReactNode {
  return value as ReactNode;
}

/**
 * The reviewer-row list, shared by AssessmentScorecard (when a full dimension
 * scorecard is available) and InvestmentMemoContent's bare fallback (when it
 * isn't — no structuredScoring yet, or the fund's config disables score
 * reasoning). Previously implemented twice; they had already drifted (only one
 * showed `coverage`, only the other showed the spread/conviction line) before
 * being consolidated here.
 */
export default function ReviewerPanel({ rows, consensus, renderNumbers = identity }: ReviewerPanelProps) {
  if (rows.length === 0) return null;

  const { min, max, spread, split } = consensus;
  const spreadLine =
    min != null && max != null
      ? min === max
        ? `${min.toFixed(1)}/10 across the panel`
        : `${min.toFixed(1)}–${max.toFixed(1)}/10 spread`
      : null;

  return (
    <div className="memoScorePanel">
      <div className="memoConsensusHead">
        {/* Flag only the exception: a split panel is the signal worth surfacing; an
            aligned panel is the expected case, so it gets a quiet label, not a verdict. */}
        {split ? (
          <p className="memoConsensusFlag">Reviewers split</p>
        ) : (
          <p className="memoConsensusLabel">Reviewer panel</p>
        )}
        {spreadLine ? (
          <p className="memoConsensusSpread">
            {renderNumbers(spreadLine)}
            {spread != null && spread >= 2 ? '  ·  conviction diverges' : ''}
          </p>
        ) : null}
      </div>
      <p className="memoScoreSub">
        One model, one evidence packet, three prompted postures — not independent reviews.
      </p>
      <ul className="memoConsensusList">
        {rows.map((row) => (
          <li key={row.key} className="memoConsensusRow">
            <span className="memoConsensusName" title={REVIEWER_POSTURES[row.key]}>
              {row.name}
            </span>
            <span className="memoConsensusScore">
              {row.score != null ? renderNumbers(row.score.toFixed(1)) : '—'}
              {row.coverage != null ? (
                <span className="memoConsensusCoverage">
                  {`${Math.round(row.coverage * 100)}% data coverage`}
                </span>
              ) : null}
            </span>
            <span className="memoConsensusTake">{renderNumbers(row.take || 'No qualitative summary.')}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
