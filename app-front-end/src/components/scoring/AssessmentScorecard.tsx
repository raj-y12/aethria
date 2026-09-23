import { useId, useState, type ReactNode } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import type {
  ScoringDimensionKey,
  ScoringPresentation,
  StructuredScoring,
} from '../../types/startup';
import type { CriterionAssessment, RecommendationState } from '../../api/evaluations';
import type { MemoClaimProvenance } from '../../lib/memoDecisionBrief';
import { getScoreBand } from '../../design-system/semantics';
import { tokens } from '../../design-system/tokens';
import { safeHref } from '../../lib/memoReferenceHref';
import { getEvidenceConfidenceLabel, isLowEvidence } from './ConfidenceIndicator';
import {
  buildComponentDrivers,
  cleanReasoningList,
} from '../../lib/scoringRationale';
import Popover from '../ui/Popover';
import ReviewerPanel, {
  type ScorecardReviewerConsensus,
  type ScorecardReviewerRow,
} from './ReviewerPanel';

export type { ScorecardReviewerConsensus, ScorecardReviewerRow };

export type ScorecardDimensionDef = {
  key: ScoringDimensionKey;
  label: string;
  id: string;
};

interface AssessmentScorecardProps {
  dimensions: ScorecardDimensionDef[];
  scoring: StructuredScoring;
  presentation?: ScoringPresentation | null;
  reviewerRows: ScorecardReviewerRow[];
  reviewerConsensus: ScorecardReviewerConsensus;
  renderNumbers?: (value: unknown) => ReactNode;
  reduceMotion?: boolean;
  /** Canonical score provenance, supplied only when the scorecard is backed by
   * an immutable evaluation. This is deliberately separate from legacy review
   * components so the UI never invents a ledger for historical scores. */
  canonicalCriteria?: CriterionAssessment[];
  canonicalClaims?: MemoClaimProvenance[];
  canonicalRecommendationState?: RecommendationState | null;
  canonicalRubricVersion?: string | null;
}

const METHOD_COPY = [
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
  canonicalCriteria = [],
  canonicalClaims = [],
  canonicalRecommendationState = null,
}: AssessmentScorecardProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const idPrefix = useId();
  const toggle = (key: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const insufficientEvidence = canonicalRecommendationState === 'insufficient_evidence';
  const overallScore = insufficientEvidence ? null : (presentation?.overall_score ?? scoring.overall_score);
  const overallBand = insufficientEvidence
    ? 'Not scored'
    : (presentation?.overall_band ?? getScoreBand(scoring.overall_score, presentation?.score_bands ?? undefined).label);
  const bandCopy = (presentation?.score_bands ?? [])
    .map((band) => `${band.min}–${band.max} ${band.label}`)
    .join(' · ');
  const methodCopy = [
    canonicalCriteria.some((criterion) => criterion.deterministic_adjustments?.assessment_validation)
      ? 'Reviewer proposes each dimension score with an investment rationale. Evidence validation may cap it or leave it unscored when support is insufficient. Partner makes the recommendation from the completed review.'
      : `Historical evidence-based scoring: each dimension is scored 1–10 from extracted evidence${bandCopy ? ` — bands: ${bandCopy}.` : '.'}`,
    ...METHOD_COPY,
    presentation?.stage_cohort_label ? `Stage cohort: ${presentation.stage_cohort_label}.` : null,
    presentation?.sector_tam_benchmark ? `Market TAM benchmark: ${presentation.sector_tam_benchmark}.` : null,
  ].filter((line): line is string => Boolean(line));

  // Driver-score dispersion (audit): the overall is a mean, so a flat 7 and a lopsided
  // [9,9,3,9] share a headline. Surface the spread so a reader sees the profile is uneven.
  const dispersion = scoring.overall_dispersion;
  const dispersionLine =
    dispersion && dispersion.range >= 2.5
      ? `Uneven profile — drivers span ${dispersion.min.toFixed(1)}–${dispersion.max.toFixed(1)}/10`
      : dispersion
        ? `Balanced profile — drivers within ${dispersion.range.toFixed(1)} pts`
        : null;

  // Defensibility is a moat SIGNAL, not a driver — it is excluded from the overall mean
  // (OVERALL_SCORE_DIMENSIONS). Render it apart from the four drivers so the layout never
  // implies it feeds the headline score. Split by key, not array position.
  const driverDims = dimensions.filter((d) => d.key !== 'defensibility');
  const moatDims = dimensions.filter((d) => d.key === 'defensibility');

  const scoreBasis = driverDims
    .map((dim) => {
      const source = presentation?.dimensions?.find((item) => item.id === dim.key);
      const dimension = scoring[dim.key];
      const score = source?.score ?? (dimension.unscored ? null : dimension.score);
      return score == null ? null : `${dim.label} ${score.toFixed(1)}`;
    })
    .filter((value): value is string => Boolean(value));

  const renderRow = (dim: ScorecardDimensionDef) => {
    const dimension = scoring[dim.key];
    if (!dimension) return null;
    const presDim = presentation?.dimensions?.find((d) => d.id === dim.key);
    const canonicalCriterion = canonicalCriteria.find((criterion) => criterion.criterion === dim.key);
    const validation = canonicalCriterion?.deterministic_adjustments?.assessment_validation;
    const priorReview = canonicalCriterion?.deterministic_adjustments?.change_from_prior_review;
    const criterionClaims = canonicalClaims.filter((claim) => claim.criterion === dim.key);
    const unscored = !presDim && dimension.unscored === true;
    const scoreText = unscored
      ? 'Not scored'
      : presDim
        ? presDim.score.toFixed(1)
        : dimension.score.toFixed(1);
    const lowConfidence = !presDim && !unscored && isLowEvidence(dimension.confidence);
    // The governed scoring engine resolves three personas' reads per dimension; when they
    // diverge past the material-spread threshold it pulls the score toward the lowest read
    // instead of a straight average and records that as "conservative_mean_floor". Surface
    // that as a flag on the specific dimension it happened to, not just an aggregate panel
    // spread — a reader needs to know WHICH number to distrust, not just that some pair of
    // reviewers disagreed somewhere.
    // Independent of presDim: the legacy presentation overlay's text is a generic
    // sufficiency message, not a disagreement signal, so it must not suppress this flag
    // the way it suppresses lowConfidence's overlapping "evidence is thin" message.
    const personaResolution = dimension.components?.persona_resolution;
    const disputed = !unscored && personaResolution?.strategy === 'conservative_mean_floor';
    const allDrivers = buildComponentDrivers(dimension.components ?? {});
    // Separate what the score rests on from what's still unknown, so an analyst can see
    // "this 5.8 is 1 real signal + 4 gaps" at a glance rather than a flat undifferentiated list.
    const evidence = allDrivers.filter((d) => d.status !== 'missing');
    const gaps = allDrivers.filter((d) => d.status === 'missing');
    const reasoning = allDrivers.length === 0 ? cleanReasoningList(dimension.reasoning) : [];
    const weaknesses = cleanReasoningList(dimension.weaknesses);
    const take = reasoning[0] ?? evidence[0]?.text ?? gaps[0]?.text ?? weaknesses[0] ?? (
      unscored ? 'Required evidence is not available for this dimension.' : 'Score recorded; supporting detail is available below.'
    );
    const isOpen = expanded.has(dim.key);
    const hasCanonicalLedger = Boolean(canonicalCriterion);
    const hasDetail =
      evidence.length > 0 || gaps.length > 0 || reasoning.length > 0 || weaknesses.length > 0 || lowConfidence || unscored || disputed || hasCanonicalLedger;

    const renderDriver = (d: (typeof allDrivers)[number]) => (
      <li key={d.id} className="memoScoreDriverItem">
        <span className="memoScoreDriverHead">
          <span className="memoScoreDriverName">{d.label}</span>
          {d.tag && <span className="memoScoreDriverTag">{d.tag}</span>}
        </span>
        {d.score != null && (
          <span className="memoScoreDriverText memoScoreDriverMeta">
            {renderNumbers(`${d.score.toFixed(1)}/10 · ${d.qualitative ? 'qualitative judgment' : `${Math.round((d.confidence ?? 0) * 100)}% confidence`}`)}
          </span>
        )}
        {d.text && <span className="memoScoreDriverText">{renderNumbers(d.text)}</span>}
        {d.evidence && <span className="memoScoreDriverText">{renderNumbers(`Evidence: ${d.evidence}`)}</span>}
        {d.rule && <span className="memoScoreDriverText">{renderNumbers(`Rule: ${d.rule}`)}</span>}
      </li>
    );

    const detailId = `${idPrefix}-${dim.key}-detail`;
    return (
      <li key={dim.key}>
        <button
          type="button"
          onClick={() => hasDetail && toggle(dim.key)}
          aria-expanded={isOpen}
          aria-controls={hasDetail ? detailId : undefined}
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
          <span className="memoScoreView">View details</span>
          {hasDetail && (
            <span aria-hidden className={isOpen ? 'memoScoreChevron memoScoreChevron--open' : 'memoScoreChevron'}>
              ›
            </span>
          )}
        </button>
        <p className="memoScoreTake">{renderNumbers(take)}</p>

        <AnimatePresence initial={false}>
          {isOpen && hasDetail && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={reduceMotion ? { duration: 0 } : { duration: 0.22, ease: tokens.motion.ease }}
              style={{ overflow: 'hidden' }}
            >
              <div id={detailId} role="region" aria-label={`${dim.label} detail`} className="memoScoreDetail">
                {canonicalCriterion && (
                  <div className="memoScoreLedger" aria-label={`${dim.label} score ledger`}>
                    <p className="memoScoreGroupLabel">Score ledger</p>
                    {validation ? (
                      <>
                        <p className="memoScoreEvidenceNote">
                          {`Reviewer assessment: ${validation.proposed_score == null ? 'not scored' : `${validation.proposed_score.toFixed(1)}/10`}. Validated: ${canonicalCriterion.score == null ? 'not scored' : `${canonicalCriterion.score.toFixed(1)}/10`}.`}
                        </p>
                        {validation.cap_reason && <p className="memoScoreEvidenceNote">{validation.cap_reason}</p>}
                        {priorReview?.score_changed && (
                          <p className="memoScoreEvidenceNote">
                            {`Previous review: ${priorReview.previous_score == null ? 'not scored' : `${priorReview.previous_score.toFixed(1)}/10`}.`}
                          </p>
                        )}
                        {priorReview?.reasoning_changed && priorReview.previous_reasoning && (
                          <p className="memoScoreEvidenceNote">Previous reasoning: {priorReview.previous_reasoning}</p>
                        )}
                        {validation.contradiction_status === 'PRESENT' && (
                          <p className="memoScoreEvidenceNote">Conflicting evidence requires diligence.</p>
                        )}
                      </>
                    ) : canonicalCriterion.score == null ? (
                      <p className="memoScoreEvidenceNote">Not scored: {canonicalCriterion.missing_evidence.join('; ') || 'no eligible cited claim.'}</p>
                    ) : (
                      <p className="memoScoreEvidenceNote">
                        Formula: lowest eligible policy anchor
                        {Array.isArray(canonicalCriterion.deterministic_adjustments?.eligible_anchor_scores)
                          ? ` (${canonicalCriterion.deterministic_adjustments.eligible_anchor_scores.join(', ')})`
                          : ''}
                        {`. Result: ${canonicalCriterion.score.toFixed(1)}/10.`}
                      </p>
                    )}
                    {criterionClaims.length > 0 && (
                      <ul className="memoScoreReasonList">
                        {criterionClaims.map((claim) => (
                          <li key={`${claim.claimId}-${claim.relationship}`} className="memoScoreReason">
                            <span>{renderNumbers(`${claim.relationship === 'supports' ? 'Supports' : 'Contradicts'}: ${claim.claim}`)}</span>
                            {claim.sources.length > 0 && (
                              <span className="memoScoreDriverText memoScoreDriverMeta">
                                Sources: {claim.sources.map((source, index) => (
                                  <span key={source.artifactId}>
                                    {index > 0 ? ' · ' : ''}
                                    {source.href ? <a href={safeHref(source.href)} target="_blank" rel="noreferrer">{source.title}</a> : source.title}
                                  </span>
                                ))}
                              </span>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
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
                {disputed && (
                  <p className="memoScoreEvidenceNote">
                    Reviewers read this dimension differently
                    {typeof personaResolution?.spread === 'number'
                      ? ` (spread ${personaResolution.spread.toFixed(1)} pts)`
                      : ''}
                    ; the score was pulled toward the most conservative read rather than
                    averaged straight — treat it as less settled than the number implies.
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
      {/* Headline — only show a figure when an overall score is actually available. */}
      <div className="memoScoreHead">
        {overallScore != null ? (
          <p className="memoScoreHeadline">
            <span className="memoScoreHeadlineValue">{renderNumbers(overallScore.toFixed(1))}</span>
            <span className="memoScoreHeadlineMax">/ 10</span>
            <span className="memoScoreHeadlineTag">{overallBand}</span>
          </p>
        ) : null}
        <Popover
          reduceMotion={reduceMotion}
          align="end"
          label="How this was scored"
          triggerClassName="memoScoreMethod"
          content={
            <div className="space-y-1.5">
              <p className="type-label-section">How this was scored</p>
              {methodCopy.map((line, i) => (
                <p key={i} className="type-note leading-relaxed text-oxford/[0.72]">{renderNumbers(line)}</p>
              ))}
            </div>
          }
        >
          How scored
        </Popover>
      </div>
      <p className="memoScoreBasis">
        {insufficientEvidence ? (
          'Overall unavailable: required evidence is missing or contradictory.'
        ) : (
          <>
            <strong>Score basis:</strong>{' '}
            {scoreBasis.length > 0
              ? `${scoreBasis.join(' + ')}; overall is the mean of these scored dimensions. Unscored dimensions are excluded.`
              : 'No driver has enough supporting evidence to contribute to the overall score.'}
          </>
        )}
      </p>
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

      <ReviewerPanel rows={reviewerRows} consensus={reviewerConsensus} renderNumbers={renderNumbers} />
    </div>
  );
}
