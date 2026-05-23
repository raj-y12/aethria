import type { ScoringDimension } from '../../types/startup';
import { useMemo, useState } from 'react';
import { getScoreBand } from '../../design-system/semantics';
import ConfidenceIndicator, { formatConfidencePercent, normalizeConfidence } from './ConfidenceIndicator';

interface DimensionCardProps {
  id: string;
  title: string;
  dimension: ScoringDimension;
}

const DIMENSION_WEIGHTS: Record<string, Record<string, number>> = {
  market: { tam: 0.3, growth_rate: 0.2, urgency: 0.15, timing: 0.15, competition: 0.2 },
  execution: { traction: 0.3, growth_velocity: 0.2, gtm_effectiveness: 0.2, team_execution: 0.15, operational_velocity: 0.15 },
  product: { value_prop: 0.25, pain_alignment: 0.25, differentiation: 0.2, ux: 0.15, retention: 0.15 },
  technical: { complexity: 0.25, engineering_quality: 0.2, scalability: 0.2, data_advantage: 0.2, architecture: 0.15 },
  defensibility: { network_effects: 0.25, switching_costs: 0.2, proprietary_data: 0.2, barriers: 0.2, brand: 0.15 },
};

const DIMENSION_KEY_BY_TITLE: Record<string, string> = {
  Market: 'market',
  Execution: 'execution',
  Product: 'product',
  Technical: 'technical',
  Defensibility: 'defensibility',
};

const DRIVER_LABELS: Record<string, string> = {
  architecture: 'Architecture',
  barriers: 'Barriers to entry',
  brand: 'Brand leverage',
  competition: 'Competitive pressure',
  complexity: 'Technical complexity',
  data_advantage: 'Data advantage',
  defensibility: 'Defensibility',
  differentiation: 'Differentiation',
  engineering_quality: 'Engineering quality',
  growth_rate: 'Growth rate',
  growth_velocity: 'Growth velocity',
  gtm_effectiveness: 'GTM effectiveness',
  market: 'Market',
  network_effects: 'Network effects',
  operational_velocity: 'Operational velocity',
  pain_alignment: 'Pain alignment',
  product: 'Product',
  proprietary_data: 'Proprietary data',
  retention: 'Retention',
  scalability: 'Scalability',
  switching_costs: 'Switching costs',
  tam: 'Market size',
  team_execution: 'Team execution',
  technical: 'Technical',
  timing: 'Timing',
  traction: 'Traction',
  urgency: 'Customer urgency',
  ux: 'User experience',
  value_prop: 'Value proposition',
};

function prettyName(name: string): string {
  return DRIVER_LABELS[name] ?? name
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function clampScore(score: number): number {
  return Math.max(0, Math.min(10, score));
}

function scoreDescriptor(score: number, missing = false): string {
  if (missing) return 'Missing';
  if (score >= 8) return 'Strong';
  if (score >= 7) return 'Promising';
  if (score >= 6) return 'Mixed';
  if (score >= 4) return 'Weak';
  return 'Concerning';
}

function sentenceFromItems(items: string[], fallback: string): string {
  const clean = items.map((item) => item.trim().replace(/[.;,\s]+$/, '')).filter(Boolean);
  if (!clean.length) return fallback;
  return `${clean.slice(0, 3).join(', ')}.`;
}

function statusIsMissing(status: string | null | undefined): boolean {
  return String(status ?? '').toLowerCase().includes('missing');
}

function componentIsMissing(component: { value?: string | null; label?: string | null; evidence?: string | null; reasoning?: string | null }): boolean {
  const value = String(component.value ?? '').trim();
  const label = String(component.label ?? '').trim();
  const evidence = String(component.evidence ?? '').trim();
  const reasoning = String(component.reasoning ?? '').trim().toLowerCase();
  return (!value && !label && !evidence) || reasoning.includes('missing input') || reasoning.includes('missing evidence');
}

function confidenceTone(confidence: number | null): string {
  if (confidence == null) return 'Unknown confidence';
  if (confidence < 0.4) return 'Low confidence';
  if (confidence < 0.75) return 'Medium confidence';
  return 'High confidence';
}

export default function DimensionCard({ id, title, dimension }: DimensionCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [calculationOpen, setCalculationOpen] = useState(false);
  const criteriaEntries = Object.entries(dimension.criteria ?? {});
  const entries = Object.entries(dimension.components ?? {});
  const hasCriteria = criteriaEntries.length > 0;
  const hasComponents = entries.length > 0;
  const reasoning = (dimension.reasoning ?? []).filter((s) => typeof s === 'string' && s.trim().length > 0);
  const weaknesses = (dimension.weaknesses ?? []).filter((s) => typeof s === 'string' && s.trim().length > 0);
  const scoreLabel = typeof dimension.score_label === 'string' && dimension.score_label.trim().length > 0
    ? dimension.score_label.trim()
    : null;
  const hasNarrative = reasoning.length > 0 || weaknesses.length > 0 || !!scoreLabel;
  const hasDetail = hasCriteria || hasComponents || hasNarrative;
  const band = getScoreBand(dimension.score).label;
  const dimKey = DIMENSION_KEY_BY_TITLE[title] ?? title.toLowerCase();
  const weights = DIMENSION_WEIGHTS[dimKey] ?? {};
  const confidenceLabel = formatConfidencePercent(dimension.confidence);
  const normalizedConfidence = normalizeConfidence(dimension.confidence);
  const lowConfidence = normalizedConfidence != null && normalizedConfidence < 0.4;
  const scoreText = lowConfidence ? String(Math.round(dimension.score)) : dimension.score.toFixed(1);
  const displayLabel = scoreLabel ?? band;
  const allDriverRows = useMemo(() => {
    const fromCriteria = criteriaEntries.map(([name, criterion]) => {
      const missing = criterion.missing_data_applied || statusIsMissing(criterion.evidence_status);
      const score = clampScore(criterion.score);
      return {
        key: name,
        label: criterion.name || prettyName(name),
        score,
        scoreText: missing ? 'Missing' : score.toFixed(1),
        tone: scoreDescriptor(score, missing),
        missing,
        reasoning: criterion.reasoning,
        source: criterion.source_components,
        weight: criterion.weight,
        evidence: criterion.evidence_status,
      };
    });
    const fromComponents = entries.map(([name, component]) => {
      const missing = componentIsMissing(component);
      const score = clampScore(component.score);
      return {
        key: name,
        label: prettyName(name),
        score,
        scoreText: missing ? 'Missing' : score.toFixed(1),
        tone: scoreDescriptor(score, missing),
        missing,
        reasoning: component.reasoning || component.evidence || 'No rationale recorded.',
        source: component.rule ? [component.rule] : [],
        weight: weights[name] != null ? weights[name] * 100 : 0,
        evidence: component.label || component.value || component.evidence || null,
      };
    });
    const rows = fromCriteria.length > 0 ? fromCriteria : fromComponents;
    return rows.sort((a, b) => {
      if (a.missing !== b.missing) return a.missing ? 1 : -1;
      return b.score - a.score;
    });
  }, [criteriaEntries, entries, weights]);
  const driverRows = allDriverRows.slice(0, 5);
  const supports = driverRows
    .filter((row) => !row.missing && row.score >= 7)
    .map((row) => row.label);
  const weakens = [
    ...driverRows.filter((row) => !row.missing && row.score < 7).map((row) => row.label),
    ...weaknesses.slice(0, 2),
  ];
  const missingEvidence = allDriverRows
    .filter((row) => row.missing)
    .map((row) => row.label);
  const rationaleText = reasoning[0]
    ?? driverRows.find((row) => !row.missing)?.reasoning
    ?? `${title} receives a ${displayLabel.toLowerCase()} read based on the available evidence.`;
  const meaningText = lowConfidence
    ? `${displayLabel} ${title.toLowerCase()} signal, but conviction is reduced by missing or thin evidence.`
    : `${displayLabel} ${title.toLowerCase()} signal supported by the strongest available evidence.`;

  return (
    <article id={id} className="memoDocDimensionCard">
      <div className="memoDocDimensionHeader">
        <div className="memoDocDimensionTopline">
          <div className="memoDocDimensionTitleGroup">
            <div className="memoDocDimensionTitleRow">
              <p className="memoDocScorePanelTitle">{title}</p>
              <span className="memoDocScoreBandTag">{displayLabel}</span>
            </div>
            <div className="memoDocDimensionScoreRow">
              <p className="memoDocScorePanelNumber">{scoreText}</p>
              <p className="memoDocScorePanelMeta">{confidenceTone(normalizedConfidence)}, {confidenceLabel}</p>
            </div>
          </div>
          {hasDetail && (
            <button
              type="button"
              onClick={() => {
                setIsExpanded((prev) => !prev);
                if (isExpanded) setCalculationOpen(false);
              }}
              className="memoDocTooltipBtn memoDocDimensionDetailBtn"
              aria-expanded={isExpanded}
              aria-controls={`${id}-components`}
            >
              {isExpanded ? 'Close rationale' : 'Read rationale'}
            </button>
          )}
        </div>
        <ConfidenceIndicator confidence={dimension.confidence} />
      </div>
      {hasDetail && (
        <div
          id={`${id}-components`}
          className={isExpanded ? 'memoScoreRationale' : 'hidden'}
          aria-hidden={!isExpanded}
        >
          <div className="memoScoreRationaleLead">
            <p className="memoScoreRationaleTitle">Why this score</p>
            <p className="memoScoreRationaleBody">{rationaleText}</p>
            <p className="memoScoreRationaleMeaning">{meaningText}</p>
            {lowConfidence && (
              <p className="memoScoreLowConfidence">
                Low confidence: treat this score as directional until evidence improves.
              </p>
            )}
          </div>

          <dl className="memoScoreEvidenceSummary">
            <div>
              <dt>Supports score</dt>
              <dd>{sentenceFromItems(supports, 'No strong positive drivers were isolated in the available score detail.')}</dd>
            </div>
            <div>
              <dt>Weakens score</dt>
              <dd>{sentenceFromItems(weakens, 'No clear weakening driver was recorded.')}</dd>
            </div>
            <div>
              <dt>Missing evidence</dt>
              <dd>{sentenceFromItems(missingEvidence, 'No missing evidence was flagged for this dimension.')}</dd>
            </div>
          </dl>

          {driverRows.length > 0 && (
            <div className="memoScoreDriverTable" aria-label={`${title} score drivers`}>
              {driverRows.map((row) => (
                <div key={`${id}-${row.key}`} className={`memoScoreDriverRow${row.missing ? ' memoScoreDriverRow--missing' : ''}`}>
                  <span className="memoScoreDriverName">{row.label}</span>
                  <span className="memoScoreDriverScore">{row.scoreText}</span>
                  <span className="memoScoreDriverTone">{row.tone}</span>
                </div>
              ))}
            </div>
          )}

          {(hasCriteria || hasComponents || hasNarrative) && (
            <details
              className="memoScoreCalculation"
              open={calculationOpen}
              onToggle={(event) => setCalculationOpen(event.currentTarget.open)}
            >
              <summary>Calculation detail</summary>
              <div className="memoScoreCalculationBody">
                {criteriaEntries.map(([name, criterion]) => (
                  <div key={`${id}-calc-${name}`} className="memoScoreCalculationRow">
                    <p className="memoScoreCalculationName">{criterion.name || prettyName(name)}</p>
                    <p>Weight {Math.round(criterion.weight)}%. Evidence {criterion.evidence_status}. Score {clampScore(criterion.score).toFixed(1)}.</p>
                    {criterion.missing_data_applied && <p>Missing data penalty applied.</p>}
                    {criterion.source_components?.length > 0 && <p>Policy inputs: {criterion.source_components.map(prettyName).join(', ')}.</p>}
                    <p>{criterion.reasoning}</p>
                  </div>
                ))}
                {entries.map(([name, component]) => (
                  <div key={`${id}-calc-component-${name}`} className="memoScoreCalculationRow">
                    <p className="memoScoreCalculationName">{prettyName(name)}</p>
                    <p>Weight {Math.round((weights[name] ?? 0) * 100)}%. Score {clampScore(component.score).toFixed(1)}.</p>
                    {component.rule && <p>Rule: {component.rule}.</p>}
                    {(component.label || component.value) && <p>Raw value: {component.label || component.value}.</p>}
                    {component.evidence && <p>Evidence: {component.evidence}</p>}
                    <p>{component.reasoning}</p>
                  </div>
                ))}
                {!hasCriteria && !hasComponents && reasoning.map((item, i) => (
                  <p key={`${id}-calc-r-${i}`} className="memoScoreCalculationRow">{item}</p>
                ))}
              </div>
            </details>
            )}
        </div>
      )}
    </article>
  );
}
