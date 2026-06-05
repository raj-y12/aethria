import type { ReactNode } from 'react';
import type {
  ScoringDimensionKey,
  ScoringPresentation,
  StructuredScoring,
} from '../../types/startup';
import { getScoreBand } from '../../design-system/semantics';
import { getEvidenceConfidenceLabel, isLowEvidence } from './ConfidenceIndicator';
import {
  buildComponentDrivers,
  cleanReasoningList,
  dimensionBriefTake,
  takeFirst,
} from '../../lib/scoringRationale';
import Popover from '../ui/Popover';

export type ScorecardDimensionDef = {
  key: ScoringDimensionKey;
  label: string;
  id: string;
};

export type ScorecardReviewerRow = {
  key: string;
  name: string;
  score: number | null;
  verdict?: string;
  take?: string;
};

export type ScorecardReviewerConsensus = {
  min: number | null;
  max: number | null;
  spread: number | null;
  split: boolean;
  verdict?: string | null;
};

interface AssessmentScorecardProps {
  dimensions: ScorecardDimensionDef[];
  scoring: StructuredScoring;
  presentation?: ScoringPresentation | null;
  reviewerRows: ScorecardReviewerRow[];
  reviewerConsensus: ScorecardReviewerConsensus;
  renderNumbers?: (value: unknown) => ReactNode;
  reduceMotion?: boolean;
}

const METHOD_COPY = [
  'Each dimension is scored 1–10 from extracted evidence — bands: 1–3 Weak · 4–5 Concerning · 6–7 Promising · 8–10 Strong.',
  'Overall = mean of Market, Product, Technical, Execution. Defensibility is a separate moat signal and is not averaged in.',
  'A dimension with no supporting evidence reads “Not scored” and is excluded from the overall. Evidence labels (Limited → Extensive) describe how well-supported a score is, separately from the score.',
];

function identity(value: unknown): ReactNode {
  return value as ReactNode;
}

/**
 * One declarative assessment block: a static scorecard (all dimensions visible, no tabs),
 * per-row rationale on hover, and the reviewer panel inlined. Replaces the former
 * tab-strip + per-dimension accordions + separate consensus + reviewer-detail tabs.
 */
export default function AssessmentScorecard({
  dimensions,
  scoring,
  presentation,
  reviewerRows,
  reviewerConsensus,
  renderNumbers = identity,
  reduceMotion = false,
}: AssessmentScorecardProps) {
  const overallScore = presentation?.overall_score ?? scoring.overall_score;
  const overallBand = presentation?.overall_band ?? getScoreBand(scoring.overall_score).label;
  const evidenceLabel =
    presentation?.confidence_label ?? getEvidenceConfidenceLabel(scoring.overall_confidence);
  const headlineParts = [
    `${overallScore.toFixed(1)} / 10`,
    overallBand,
    evidenceLabel ? `${evidenceLabel} evidence` : null,
  ].filter(Boolean) as string[];

  const { min, max, spread, split, verdict } = reviewerConsensus;
  const spreadLine =
    min != null && max != null
      ? min === max
        ? `${min.toFixed(1)}/10 across the panel`
        : `${min.toFixed(1)}–${max.toFixed(1)}/10 spread`
      : null;

  return (
    <div className="memoAssessmentCard">
      {/* Headline */}
      <div className="flex items-baseline justify-between gap-3">
        <p className="type-data text-oxford/88">{renderNumbers(headlineParts.join('   ·   '))}</p>
        <Popover
          reduceMotion={reduceMotion}
          align="end"
          label="How this was scored"
          triggerClassName="type-meta uppercase tracking-[0.08em] text-oxford/45 hover:text-oxford/70"
          content={
            <div className="space-y-1.5">
              <p className="type-meta uppercase tracking-[0.08em] text-oxford/55">How this was scored</p>
              {METHOD_COPY.map((line, i) => (
                <p key={i} className="type-note leading-relaxed text-oxford/72">{renderNumbers(line)}</p>
              ))}
            </div>
          }
        >
          How scored
        </Popover>
      </div>

      {/* Dimension scorecard — all visible, rationale on hover */}
      <ul className="mt-3 divide-y divide-oxford/8 border-y border-oxford/8">
        {dimensions.map((dim) => {
          const dimension = scoring[dim.key];
          if (!dimension) return null;
          const presDim = presentation?.dimensions?.find((d) => d.id === dim.key);
          const unscored = !presDim && dimension.unscored === true;
          const scoreText = unscored
            ? 'Not scored'
            : presDim
              ? presDim.score.toFixed(1)
              : dimension.score.toFixed(1);
          const lowConfidence = !presDim && !unscored && isLowEvidence(dimension.confidence);
          const take = unscored
            ? 'No supporting evidence — excluded from the overall.'
            : dimensionBriefTake(dimension, presDim);

          const drivers = takeFirst(buildComponentDrivers(dimension.components ?? {}), 3).shown;
          const reasoning = drivers.length === 0 ? takeFirst(cleanReasoningList(dimension.reasoning), 3).shown : [];
          const weaknesses = takeFirst(cleanReasoningList(dimension.weaknesses), 2).shown;

          return (
            <li key={dim.key}>
              <Popover
                reduceMotion={reduceMotion}
                className="w-full"
                triggerClassName="memoScorecardRow group flex w-full items-baseline gap-3 py-2.5 text-left"
                content={
                  <div className="space-y-2">
                    <p className="type-meta uppercase tracking-[0.08em] text-oxford/55">
                      {dim.label} · {renderNumbers(unscored ? 'Not scored' : `${scoreText} / 10`)}
                    </p>
                    {drivers.length > 0 && (
                      <ul className="space-y-1.5">
                        {drivers.map((d) => (
                          <li key={d.id} className="type-note leading-relaxed text-oxford/75">
                            <span className="text-oxford/55">{d.label}: </span>
                            {renderNumbers(d.text || '—')}
                          </li>
                        ))}
                      </ul>
                    )}
                    {reasoning.length > 0 && (
                      <ul className="space-y-1.5">
                        {reasoning.map((text, i) => (
                          <li key={i} className="type-note leading-relaxed text-oxford/75">{renderNumbers(text)}</li>
                        ))}
                      </ul>
                    )}
                    {weaknesses.length > 0 && (
                      <div className="space-y-1">
                        <p className="type-meta uppercase tracking-[0.08em] text-oxford/45">Watch</p>
                        {weaknesses.map((text, i) => (
                          <p key={i} className="type-note leading-relaxed text-oxford/70">{renderNumbers(text)}</p>
                        ))}
                      </div>
                    )}
                    {(lowConfidence || unscored) && (
                      <p className="type-meta text-oxford/50">
                        {unscored
                          ? 'No supporting evidence for this dimension.'
                          : `${getEvidenceConfidenceLabel(dimension.confidence)} evidence — score may shift with diligence.`}
                      </p>
                    )}
                  </div>
                }
              >
                <span className="w-[7.5rem] shrink-0 type-label uppercase tracking-[0.06em] text-oxford/70">
                  {dim.label}
                </span>
                <span
                  className={[
                    'w-12 shrink-0 type-data tabular-nums',
                    unscored ? 'text-oxford/35' : lowConfidence ? 'text-oxford/45' : 'text-oxford/85',
                  ].join(' ')}
                >
                  {renderNumbers(scoreText)}
                </span>
                <span className="flex-1 type-note leading-snug text-oxford/62 group-hover:text-oxford/80">
                  {renderNumbers(take)}
                  {lowConfidence && <span className="ml-1.5 type-meta text-oxford/45">· low evidence</span>}
                </span>
              </Popover>
            </li>
          );
        })}
      </ul>

      {/* Reviewer panel — inlined, static */}
      {reviewerRows.length > 0 && (
        <div className="mt-4">
          <p className="type-meta uppercase tracking-[0.08em] text-oxford/50">
            The panel
            <span className="text-oxford/72">{`   ·   ${split ? 'Split' : 'Aligned'}`}</span>
            {verdict ? <span className="text-oxford/72">{`   ·   ${verdict}`}</span> : null}
            {spreadLine ? <span className="text-oxford/55">{renderNumbers(`   ·   ${spreadLine}`)}</span> : null}
            {spread != null && spread >= 2 ? <span className="text-oxford/45"> · conviction diverges</span> : null}
          </p>
          <ul className="mt-2 space-y-1.5">
            {reviewerRows.map((row) => (
              <li key={row.key} className="flex items-baseline gap-3">
                <span className="w-24 shrink-0 type-label uppercase tracking-[0.05em] text-oxford/68">{row.name}</span>
                <span className="w-16 shrink-0 type-meta uppercase tracking-[0.06em] text-oxford/55">{row.verdict ?? '—'}</span>
                <span className="w-10 shrink-0 type-data tabular-nums text-oxford/78">
                  {row.score != null ? renderNumbers(row.score.toFixed(1)) : '—'}
                </span>
                <span className="flex-1 type-note leading-snug text-oxford/60">{renderNumbers(row.take || '—')}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
