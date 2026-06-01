import type { PresentationDimension, ScoringDimension } from '../../types/startup';
import { useState } from 'react';
import { getScoreBand } from '../../design-system/semantics';
import {
  buildComponentDrivers,
  buildCriterionDrivers,
  cleanReasoningList,
  clipScoringText,
  mergeUniqueBullets,
  takeFirst,
  type ScoringDriverRow,
} from '../../lib/scoringRationale';

interface DimensionCardProps {
  id: string;
  title: string;
  dimension: ScoringDimension;
  presentation?: PresentationDimension | null;
  variant?: 'card' | 'detail';
  tabId?: string;
}

const BULLET_CAP = 4;
const DRIVER_CAP = 3;
const BASIS_ROW_CAP = 2;

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
        detailOnly={detailOnly}
        isExpanded={isExpanded}
        setIsExpanded={setIsExpanded}
        tabId={tabId}
      />
    );
  }

  const band = dimension.score_label ?? getScoreBand(dimension.score).label;
  const body = <StructuredRationaleView dimension={dimension} title={title} band={band} />;

  if (detailOnly) {
    return (
      <div id={id} className="memoDimensionDetailPanel" role="tabpanel" aria-labelledby={tabId}>
        {body}
      </div>
    );
  }

  return (
    <article id={id} className="memoDocDimensionCard">
      <div className="memoDocDimensionHeader">
        <button
          type="button"
          onClick={() => setIsExpanded((prev) => !prev)}
          className="memoDocTooltipBtn memoDocDimensionDetailBtn"
          aria-expanded={isExpanded}
          aria-controls={`${id}-components`}
        >
          {isExpanded ? 'Less' : 'Rationale'}
        </button>
      </div>
      <div
        id={`${id}-components`}
        className={isExpanded ? 'memoScoreRationale memoScoreRationale--compact' : 'hidden'}
        aria-hidden={!isExpanded}
      >
        {body}
      </div>
    </article>
  );
}

function CompactBullets({ items }: { items: string[] }) {
  const { shown, rest } = takeFirst(items, BULLET_CAP);
  if (shown.length === 0) return null;
  return (
    <ul className="memoScoreCompactList">
      {shown.map((item, index) => (
        <li key={index}>{item}</li>
      ))}
      {rest > 0 && <li className="memoScoreCompactMore">{`+${rest} more`}</li>}
    </ul>
  );
}

function CompactDrivers({ rows, label }: { rows: ScoringDriverRow[]; label: string }) {
  if (rows.length === 0) return null;
  const { shown, rest } = takeFirst(rows, DRIVER_CAP);

  const list = (
    <ul className="memoScoreCompactDrivers">
      {shown.map((row) => (
        <li key={row.id}>
          <span className="memoScoreCompactDriverLabel">{row.label}</span>
          {row.score != null && !row.missing ? (
            <span className="memoScoreCompactDriverScore">{row.score.toFixed(0)}</span>
          ) : null}
          {row.text ? <span className="memoScoreCompactDriverText">{row.text}</span> : null}
        </li>
      ))}
    </ul>
  );

  if (rows.length <= 2) {
    return (
      <div className="memoScoreCompactDriversBlock">
        <p className="memoScoreCompactKicker">{label}</p>
        {list}
      </div>
    );
  }

  return (
    <details className="memoScoreCompactDetails">
      <summary>{rest > 0 ? `${label} (+${rows.length})` : `${label} (${rows.length})`}</summary>
      {list}
    </details>
  );
}

function mergeEvidenceText(items: string[], maxLen = 150): string {
  const cleaned = mergeUniqueBullets(
    items
      .map((item) => clipScoringText(item, maxLen))
      .filter(Boolean)
  );
  return cleaned.slice(0, BASIS_ROW_CAP).join(' ');
}

function isSameIdea(a: string | null | undefined, b: string | null | undefined): boolean {
  const left = String(a ?? '').trim().toLowerCase();
  const right = String(b ?? '').trim().toLowerCase();
  if (!left || !right) return false;
  return left === right || left.includes(right.slice(0, 42)) || right.includes(left.slice(0, 42));
}

function ScoreBasisRows({
  rows,
}: {
  rows: Array<{ label: string; text: string; tone?: 'gap' }>;
}) {
  const shown = rows.filter((row) => row.text.trim()).slice(0, 4);
  if (shown.length === 0) return null;
  return (
    <dl className="memoScoreBasis">
      {shown.map((row) => (
        <div key={row.label} className={row.tone === 'gap' ? 'memoScoreBasisRow memoScoreBasisRow--gap' : 'memoScoreBasisRow'}>
          <dt>{row.label}</dt>
          <dd>{row.text}</dd>
        </div>
      ))}
    </dl>
  );
}

function StructuredRationaleView({
  dimension,
  title,
  band,
}: {
  dimension: ScoringDimension;
  title: string;
  band: string;
}) {
  const reasoning = cleanReasoningList(dimension.reasoning);
  const weaknesses = cleanReasoningList(dimension.weaknesses);
  const componentDrivers = buildComponentDrivers(dimension.components ?? {});
  const criterionDrivers = buildCriterionDrivers(dimension.criteria ?? {});
  const lead = reasoning[0] ?? `${band} · ${dimension.score.toFixed(1)}/10 on ${title.toLowerCase()}.`;
  const sub = reasoning[1] && reasoning[1] !== lead ? reasoning[1] : null;
  const bullets = mergeUniqueBullets(weaknesses, reasoning.slice(sub ? 2 : 1));

  return (
    <div className="memoScoreRationale memoScoreRationale--compact">
      <p className="memoScoreCompactLead">{lead}</p>
      {sub && <p className="memoScoreCompactSub">{sub}</p>}
      <CompactBullets items={bullets} />
      <CompactDrivers rows={componentDrivers} label="Drivers" />
      {criterionDrivers.length > 0 && componentDrivers.length === 0 ? (
        <CompactDrivers rows={criterionDrivers} label="Criteria" />
      ) : null}
    </div>
  );
}

interface PresentationViewProps {
  id: string;
  presentation: PresentationDimension;
  detailOnly: boolean;
  isExpanded: boolean;
  setIsExpanded: (v: boolean | ((p: boolean) => boolean)) => void;
  tabId?: string;
}

function PresentationView({
  id,
  presentation,
  detailOnly,
  isExpanded,
  setIsExpanded,
  tabId,
}: PresentationViewProps) {
  const {
    headline,
    score_interpretation,
    analyst_summary,
    score_justification,
    supports = [],
    weakens = [],
    missing_evidence = [],
    diligence_actions = [],
    analyst_review_note,
    evidence_coverage_warning,
    why_not_higher,
    components = [],
    consistency_explanation,
  } = presentation;

  const lead = clipScoringText(headline, 140);
  const detail = score_justification || analyst_summary;
  const sub =
    score_interpretation
    && score_interpretation !== lead
    && !lead.includes(score_interpretation.slice(0, 24))
      ? clipScoringText(score_interpretation, 120)
      : detail && detail !== lead && !lead.includes(detail.slice(0, 24))
        ? clipScoringText(detail, 140)
        : null;

  const missingBullets = missing_evidence.map((item) =>
    clipScoringText(`${item.label}: ${item.explanation}`, 120),
  );

  const note = analyst_review_note || evidence_coverage_warning || consistency_explanation;
  const componentDrivers: ScoringDriverRow[] = components.map((comp) => ({
    id: comp.id,
    label: comp.label,
    score: comp.has_evidence ? comp.score : null,
    text: clipScoringText(comp.interpretation, 100),
    missing: !comp.has_evidence,
  }));

  const diligence = diligence_actions.map((a) => clipScoringText(a, 120));
  const basisRows = [
    detail && !isSameIdea(detail, lead) && !isSameIdea(detail, sub)
      ? { label: 'Basis', text: clipScoringText(detail, 170) }
      : null,
    supports.length > 0
      ? { label: 'Supports', text: mergeEvidenceText(supports, 150) }
      : null,
    [...(why_not_higher ?? []), ...weakens].length > 0
      ? { label: 'Caps score', text: mergeEvidenceText([...(why_not_higher ?? []), ...weakens], 150) }
      : null,
    missingBullets.length > 0
      ? { label: 'Evidence gap', text: mergeEvidenceText(missingBullets, 140), tone: 'gap' as const }
      : null,
  ].filter((row): row is { label: string; text: string; tone?: 'gap' } => !!row && !!row.text);

  const body = (
    <div className="memoScoreRationale memoScoreRationale--compact">
      <p className="memoScoreCompactLead">{lead}</p>
      {sub && <p className="memoScoreCompactSub">{sub}</p>}
      {note && <p className="memoScoreCompactNote">{clipScoringText(note, 160)}</p>}
      <ScoreBasisRows rows={basisRows} />
      {componentDrivers.length > 0 && <CompactDrivers rows={componentDrivers} label="Drivers" />}
      {diligence.length > 0 && (
        <details className="memoScoreCompactDetails">
          <summary>{`Diligence (${diligence.length})`}</summary>
          <ul className="memoScoreCompactList">
            {diligence.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );

  if (detailOnly) {
    return (
      <div id={id} className="memoDimensionDetailPanel" role="tabpanel" aria-labelledby={tabId}>
        {body}
      </div>
    );
  }

  return (
    <article id={id} className="memoDocDimensionCard">
      <button
        type="button"
        onClick={() => setIsExpanded((prev) => !prev)}
        className="memoDocTooltipBtn memoDocDimensionDetailBtn"
        aria-expanded={isExpanded}
        aria-controls={`${id}-components`}
      >
        {isExpanded ? 'Less' : 'Rationale'}
      </button>
      <div
        id={`${id}-components`}
        className={isExpanded ? 'memoScoreRationale memoScoreRationale--compact' : 'hidden'}
        aria-hidden={!isExpanded}
      >
        {body}
      </div>
    </article>
  );
}
