import { useState, type ReactNode } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
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
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const toggle = (key: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const overallScore = presentation?.overall_score ?? scoring.overall_score;
  const overallBand = presentation?.overall_band ?? getScoreBand(scoring.overall_score).label;
  const evidenceLabel =
    presentation?.confidence_label ?? getEvidenceConfidenceLabel(scoring.overall_confidence);

  // Driver-score dispersion (audit): the overall is a mean, so a flat 7 and a lopsided
  // [9,9,3,9] share a headline. Surface the spread so a reader sees the profile is uneven.
  const dispersion = scoring.overall_dispersion;
  const dispersionLine =
    dispersion && dispersion.range >= 2.5
      ? `Uneven profile — drivers span ${dispersion.min.toFixed(1)}–${dispersion.max.toFixed(1)}/10`
      : dispersion
        ? `Balanced profile — drivers within ${dispersion.range.toFixed(1)} pts`
        : null;

  const { min, max, spread, split, verdict } = reviewerConsensus;
  const spreadLine =
    min != null && max != null
      ? min === max
        ? `${min.toFixed(1)}/10 across the panel`
        : `${min.toFixed(1)}–${max.toFixed(1)}/10 spread`
      : null;

  // Defensibility is a moat SIGNAL, not a driver — it is excluded from the overall mean
  // (OVERALL_SCORE_DIMENSIONS). Render it apart from the four drivers so the layout never
  // implies it feeds the headline score. Split by key, not array position.
  const driverDims = dimensions.filter((d) => d.key !== 'defensibility');
  const moatDims = dimensions.filter((d) => d.key === 'defensibility');

  const renderRow = (dim: ScorecardDimensionDef) => {
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

    const allDrivers = buildComponentDrivers(dimension.components ?? {});
    // Separate what the score rests on from what's still unknown, so an analyst can see
    // "this 5.8 is 1 real signal + 4 gaps" at a glance rather than a flat undifferentiated list.
    const evidence = allDrivers.filter((d) => d.status !== 'missing');
    const gaps = allDrivers.filter((d) => d.status === 'missing');
    const reasoning = allDrivers.length === 0 ? cleanReasoningList(dimension.reasoning) : [];
    const weaknesses = cleanReasoningList(dimension.weaknesses);
    const isOpen = expanded.has(dim.key);
    const hasDetail =
      evidence.length > 0 || gaps.length > 0 || reasoning.length > 0 || weaknesses.length > 0 || lowConfidence || unscored;

    const renderDriver = (d: (typeof allDrivers)[number]) => (
      <li key={d.id} className="memoScoreDriverItem">
        <span className="memoScoreDriverHead">
          <span className="memoScoreDriverName">{d.label}</span>
          {d.tag && <span className="memoScoreDriverTag">{d.tag}</span>}
        </span>
        {d.text && <span className="memoScoreDriverText">{renderNumbers(d.text)}</span>}
      </li>
    );

    return (
      <li key={dim.key}>
        <button
          type="button"
          onClick={() => hasDetail && toggle(dim.key)}
          aria-expanded={isOpen}
          disabled={!hasDetail}
          className="memoScoreRow"
        >
          <span className="memoScoreName">{dim.label}</span>
          <span
            className={
              unscored
                ? 'memoScoreVal memoScoreVal--unscored'
                : lowConfidence
                  ? 'memoScoreVal memoScoreVal--muted'
                  : 'memoScoreVal'
            }
          >
            {renderNumbers(scoreText)}
          </span>
          <span className="memoScoreTake">
            {renderNumbers(take)}
            {lowConfidence && <span className="memoScoreTakeFlag">low evidence</span>}
          </span>
          {hasDetail && (
            <span aria-hidden className={isOpen ? 'memoScoreChevron memoScoreChevron--open' : 'memoScoreChevron'}>
              ›
            </span>
          )}
        </button>

        <AnimatePresence initial={false}>
          {isOpen && hasDetail && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={reduceMotion ? { duration: 0 } : { duration: 0.22, ease: 'easeOut' }}
              style={{ overflow: 'hidden' }}
            >
              <div className="memoScoreDetail">
                {evidence.length > 0 && (
                  <div>
                    {gaps.length > 0 && <p className="memoScoreGroupLabel">Evidence</p>}
                    <ul className="memoScoreDriverList">{evidence.map(renderDriver)}</ul>
                  </div>
                )}
                {gaps.length > 0 && (
                  <div>
                    <p className="memoScoreGroupLabel">Needs diligence</p>
                    <ul className="memoScoreDriverList">{gaps.map(renderDriver)}</ul>
                  </div>
                )}
                {reasoning.length > 0 && (
                  <ul className="memoScoreReasonList">
                    {reasoning.map((text, i) => (
                      <li key={i} className="memoScoreReason">{renderNumbers(text)}</li>
                    ))}
                  </ul>
                )}
                {weaknesses.length > 0 && (
                  <div>
                    <p className="memoScoreGroupLabel">Watch</p>
                    <ul className="memoScoreReasonList">
                      {weaknesses.map((text, i) => (
                        <li key={i} className="memoScoreReason">{renderNumbers(text)}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {(lowConfidence || unscored) && (
                  <p className="memoScoreEvidenceNote">
                    {unscored
                      ? 'No supporting evidence for this dimension.'
                      : `${getEvidenceConfidenceLabel(dimension.confidence)} evidence — score may shift with diligence.`}
                  </p>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </li>
    );
  };

  return (
    <div className="memoAssessmentCard">
      {/* Headline — overall score reads as a figure, band + evidence as a quiet tag. */}
      <div className="memoScoreHead">
        <p className="memoScoreHeadline">
          <span className="memoScoreHeadlineValue">{renderNumbers(overallScore.toFixed(1))}</span>
          <span className="memoScoreHeadlineMax">/ 10</span>
          <span className="memoScoreHeadlineTag">
            {[overallBand, evidenceLabel ? `${evidenceLabel} evidence` : null].filter(Boolean).join('  ·  ')}
          </span>
        </p>
        <Popover
          reduceMotion={reduceMotion}
          align="end"
          label="How this was scored"
          triggerClassName="memoScoreMethod"
          content={
            <div className="space-y-1.5">
              <p className="type-label-section">How this was scored</p>
              {METHOD_COPY.map((line, i) => (
                <p key={i} className="type-note leading-relaxed text-oxford/[0.72]">{renderNumbers(line)}</p>
              ))}
            </div>
          }
        >
          How scored
        </Popover>
      </div>
      {dispersionLine && <p className="memoScoreSub">{renderNumbers(dispersionLine)}</p>}

      {/* Driver dimensions — these four make up the overall. Click a row to expand. */}
      <ul className="memoScoreList">{driverDims.map(renderRow)}</ul>

      {/* Defensibility — a moat signal read alongside, not averaged into the overall. */}
      {moatDims.length > 0 && (
        <div className="memoScoreMoat">
          <p className="memoScoreMoatLabel">
            Moat signal{'  ·  '}<em>not averaged into overall</em>
          </p>
          <ul className="memoScoreList memoScoreList--moat">{moatDims.map(renderRow)}</ul>
        </div>
      )}

      {/* Reviewer panel — same treatment as the prior Reviewer Consensus block. */}
      {reviewerRows.length > 0 && (
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
                {verdict ? `  ·  ${verdict}` : ''}
                {spread != null && spread >= 2 ? '  ·  conviction diverges' : ''}
              </p>
            ) : null}
          </div>
          <ul className="memoConsensusList">
            {reviewerRows.map((row) => (
              <li key={row.key} className="memoConsensusRow">
                <span className="memoConsensusName">{row.name}</span>
                <span className="memoConsensusScore">
                  {row.score != null ? renderNumbers(row.score.toFixed(1)) : '—'}
                </span>
                <span className="memoConsensusTake">{renderNumbers(row.take || row.verdict || '—')}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
