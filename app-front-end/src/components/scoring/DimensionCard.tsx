import type { PresentationDimension, ScoringDimension } from '../../types/startup';
import { useState } from 'react';
import { getScoreBand } from '../../design-system/semantics';
import ConfidenceIndicator from './ConfidenceIndicator';

interface DimensionCardProps {
  id: string;
  title: string;
  dimension: ScoringDimension;
  presentation?: PresentationDimension | null;
  variant?: 'card' | 'detail';
  tabId?: string;
}

export default function DimensionCard({
  id,
  title,
  dimension,
  presentation,
  variant = 'card',
  tabId,
}: DimensionCardProps) {
  const detailOnly = variant === 'detail';
  const [isExpanded, setIsExpanded] = useState(detailOnly);

  if (presentation) {
    return (
      <PresentationView
        id={id}
        presentation={presentation}
        dimension={dimension}
        detailOnly={detailOnly}
        isExpanded={isExpanded}
        setIsExpanded={setIsExpanded}
        tabId={tabId}
      />
    );
  }

  const band = getScoreBand(dimension.score).label;
  return (
    <article id={id} className="memoDocDimensionCard">
      <div className="memoDocDimensionHeader">
        <div className="memoDocDimensionTopline">
          <div className="memoDocDimensionTitleGroup">
            <div className="memoDocDimensionTitleRow">
              <p className="memoDocScorePanelTitle">{title}</p>
              <span className="memoDocScoreBandTag">{band}</span>
            </div>
            <div className="memoDocDimensionScoreRow">
              <p className="memoDocScorePanelNumber">{dimension.score.toFixed(1)}</p>
            </div>
          </div>
        </div>
        <ConfidenceIndicator confidence={dimension.confidence} />
      </div>
    </article>
  );
}

interface PresentationViewProps {
  id: string;
  presentation: PresentationDimension;
  dimension: ScoringDimension;
  detailOnly: boolean;
  isExpanded: boolean;
  setIsExpanded: (v: boolean | ((p: boolean) => boolean)) => void;
  tabId?: string;
}

function PresentationView({
  id,
  presentation,
  dimension,
  detailOnly,
  isExpanded,
  setIsExpanded,
  tabId,
}: PresentationViewProps) {
  const {
    label,
    score,
    band,
    headline,
    score_interpretation,
    analyst_summary,
    score_justification,
    supports,
    weakens,
    missing_evidence,
    diligence_actions,
    confidence_label,
    confidence_tooltip,
    evidence_coverage,
    evidence_coverage_warning,
    analyst_review_note,
    why_not_higher,
    components,
  } = presentation;

  const evidenceLabel = evidence_coverage || confidence_label;

  const rationaleLead = headline;
  const rationaleDetail = score_justification || analyst_summary;
  const showDetail =
    !!rationaleDetail &&
    rationaleDetail !== rationaleLead &&
    !rationaleLead.startsWith(rationaleDetail.slice(0, 40));

  const rationaleInner = (
    <>
      {/* Why this score: headline + interpretation + summary */}
      <div className="memoScoreRationaleLead">
        <p className="memoScoreRationaleTitle">Why this score</p>
        <p className="memoScoreRationaleBody memoScoreHeadline">{rationaleLead}</p>
        <p className="memoScoreRationaleMeaning">{score_interpretation}</p>
        {showDetail && (
          <p className="memoScoreAnalystSummary">{rationaleDetail}</p>
        )}
        {(analyst_review_note || evidence_coverage_warning) && (
          <p className="memoScoreAnalystNote" role="note">
            {analyst_review_note || evidence_coverage_warning}
          </p>
        )}
      </div>

      {why_not_higher && why_not_higher.length > 0 && (
        <div className="memoScoreWhyNotHigher">
          <p className="memoScoreRationaleTitle">Why not higher?</p>
          <ul className="memoScoreEvidenceList">
            {why_not_higher.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Evidence summary: supports / weakens / missing / diligence */}
      <dl className="memoScoreEvidenceSummary">
        <div>
          <dt>Supports conviction</dt>
          <dd>
            {supports.length > 0 ? (
              <ul className="memoScoreEvidenceList">
                {supports.map((item, i) => <li key={i}>{item}</li>)}
              </ul>
            ) : (
              <span className="memoScoreEvidenceEmpty">No strong supporting signals were isolated.</span>
            )}
          </dd>
        </div>
        <div>
          <dt>Weakens conviction</dt>
          <dd>
            {weakens.length > 0 ? (
              <ul className="memoScoreEvidenceList">
                {weakens.map((item, i) => <li key={i}>{item}</li>)}
              </ul>
            ) : (
              <span className="memoScoreEvidenceEmpty">No material weaknesses identified.</span>
            )}
          </dd>
        </div>
        {missing_evidence.length > 0 && (
          <div>
            <dt>Missing evidence</dt>
            <dd>
              <dl className="memoScoreMissingList">
                {missing_evidence.map((item, i) => (
                  <div key={i} className="memoScoreMissingItem">
                    <dt>{item.label}</dt>
                    <dd>{item.explanation}</dd>
                  </div>
                ))}
              </dl>
            </dd>
          </div>
        )}
        {diligence_actions.length > 0 && (
          <div>
            <dt>Next diligence actions</dt>
            <dd>
              <ul className="memoScoreDiligenceList">
                {diligence_actions.map((action, i) => <li key={i}>{action}</li>)}
              </ul>
            </dd>
          </div>
        )}
      </dl>

      {/* Analyst summary table (replaces verbose assessment detail) */}
      {components.length > 0 && (
        <table className="memoScoreAnalystTable" aria-label={`${label} drivers`}>
          <thead>
            <tr>
              <th>Driver</th>
              <th>Score</th>
              <th>Assessment</th>
            </tr>
          </thead>
          <tbody>
            {components.map((comp) => (
              <tr key={comp.id} className={!comp.has_evidence ? 'memoScoreAnalystTable--missing' : ''}>
                <td>{comp.label}</td>
                <td>{comp.has_evidence ? comp.score.toFixed(0) : '—'}</td>
                <td>{_truncateAssessment(comp.interpretation)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );

  if (detailOnly) {
    return (
      <div id={id} className="memoDimensionDetailPanel">
        <div className="memoDimensionDetailPanelMeta">
          <p className="memoDocScorePanelTitle">{label}</p>
          <p className="memoDocEvidenceConfidence" title={confidence_tooltip}>
            Evidence: {evidenceLabel}
          </p>
        </div>
        <div
          id={`${id}-components`}
          className="memoScoreRationale"
          role="tabpanel"
          aria-labelledby={tabId}
        >
          {rationaleInner}
        </div>
      </div>
    );
  }

  return (
    <article id={id} className="memoDocDimensionCard">
      <div className="memoDocDimensionHeader">
        <div className="memoDocDimensionTopline">
          <div className="memoDocDimensionTitleGroup">
            <div className="memoDocDimensionTitleRow">
              <p className="memoDocScorePanelTitle">{label}</p>
              <span className="memoDocScoreBandTag">{band}</span>
            </div>
            <div className="memoDocDimensionScoreRow">
              <p className="memoDocScorePanelNumber">{score.toFixed(1)}</p>
              <p className="memoDocEvidenceConfidence" title={confidence_tooltip}>
                Evidence: {evidenceLabel}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setIsExpanded((prev) => !prev)}
            className="memoDocTooltipBtn memoDocDimensionDetailBtn"
            aria-expanded={isExpanded}
            aria-controls={`${id}-components`}
          >
            {isExpanded ? 'Close rationale' : 'Read rationale'}
          </button>
        </div>
        <ConfidenceIndicator confidence={dimension.confidence} />
      </div>
      <div
        id={`${id}-components`}
        className={isExpanded ? 'memoScoreRationale' : 'hidden'}
        aria-hidden={!isExpanded}
      >
        {rationaleInner}
      </div>
    </article>
  );
}

function _truncateAssessment(text: string): string {
  const stripped = text.replace(/\.$/, '');
  if (stripped.length <= 65) return stripped;
  const cutoff = stripped.lastIndexOf(' ', 62);
  return stripped.slice(0, cutoff > 30 ? cutoff : 62) + '…';
}
