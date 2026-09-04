import { getScoreBand } from '../design-system/semantics';
import type { PresentationDimension, ScoringComponent, ScoringCriterion, ScoringDimension } from '../types/startup';
import { assessEvidenceStatus, sanitizeReasoning } from './reviewScoring';

/** Human-readable name for each scoring component id. The row label must be the METRIC
 *  (what is being assessed), never the assessed level — "moderate"/"prototype" as a row
 *  label is unreadable. The assessed level is carried separately as `tag`. */
const COMPONENT_LABELS: Record<string, string> = {
  // market
  tam: 'TAM', growth_rate: 'Growth rate', urgency: 'Urgency', timing: 'Timing', competition: 'Competition',
  // execution
  traction: 'Traction', growth_velocity: 'Growth velocity', gtm_effectiveness: 'Go-to-market',
  team_execution: 'Team', operational_velocity: 'Operational velocity',
  // product
  value_prop: 'Value proposition', pain_alignment: 'Pain alignment', differentiation: 'Differentiation',
  ux: 'UX', retention: 'Retention',
  // technical
  complexity: 'Complexity', engineering_quality: 'Engineering quality', scalability: 'Scalability',
  data_advantage: 'Data advantage', architecture: 'Architecture',
  // defensibility
  network_effects: 'Network effects', switching_costs: 'Switching costs',
  proprietary_data: 'Proprietary data', barriers: 'Barriers to entry', brand: 'Brand',
};

function componentLabel(id: string): string {
  const known = COMPONENT_LABELS[id];
  if (known) return known;
  const words = id.replace(/_/g, ' ').trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function collapseWhitespace(value: string): string {
  return value.replace(/\s+/g, ' ').trim();
}

// Truncation is intentionally disabled — the memo shows full text everywhere (no "…").
// Kept as a whitespace-normalizer with a compatible signature so call sites are unchanged.
export function clipScoringText(value: string, _max = 96): string {
  return collapseWhitespace(value);
}

export function takeFirst<T>(items: T[], limit: number): { shown: T[]; rest: number } {
  const shown = items.slice(0, limit);
  return { shown, rest: Math.max(0, items.length - shown.length) };
}

export function dimensionBriefTake(
  dimension: ScoringDimension,
  presentation?: PresentationDimension | null,
): string {
  if (presentation?.headline) return clipScoringText(presentation.headline, 88);
  if (presentation?.score_interpretation) return clipScoringText(presentation.score_interpretation, 88);

  const reasoning = (dimension.reasoning ?? [])
    .map((entry) => sanitizeReasoning(entry))
    .find(Boolean);
  if (reasoning) return clipScoringText(reasoning, 88);

  if (dimension.score_label) return clipScoringText(dimension.score_label, 88);

  const topComponent = Object.values(dimension.components ?? {})
    .map((component) => sanitizeReasoning(component.reasoning) ?? sanitizeReasoning(component.evidence))
    .find(Boolean);
  if (topComponent) return clipScoringText(topComponent, 88);

  return getScoreBand(dimension.score).label;
}

export type ScoringDriverRow = {
  id: string;
  /** The metric being assessed, e.g. "Competition" — human-readable, never a raw level. */
  label: string;
  /** The assessed level, e.g. "moderate" — shown as a small tag. Null when missing/none. */
  tag: string | null;
  score: number | null;
  confidence: number | null;
  text: string;
  /** Evidence status drives the Evidence-vs-Needs-diligence split in the memo. */
  status: 'complete' | 'partial' | 'missing';
  missing: boolean;
  /** True for judgment components with no objective anchor (P3.4). */
  qualitative?: boolean;
  evidence?: string | null;
  rule?: string | null;
};

export function buildComponentDrivers(components: Record<string, ScoringComponent>): ScoringDriverRow[] {
  const seenText = new Set<string>();
  return Object.entries(components)
    .map(([id, component]) => {
      const text = sanitizeReasoning(component.reasoning) ?? sanitizeReasoning(component.evidence);
      const status = assessEvidenceStatus(component);
      const rawTag = collapseWhitespace(String(component.label ?? ''));
      const tag = rawTag && !/^\[?\s*missing/i.test(rawTag) && status !== 'missing' ? rawTag : null;
      return {
        id,
        label: componentLabel(id),
        tag,
        score: typeof component.score === 'number' ? component.score : null,
        confidence: typeof component.confidence === 'number' ? component.confidence : null,
        text: text ? clipScoringText(text, 160) : '',
        status,
        missing: status === 'missing',
        qualitative: component.qualitative === true,
        evidence: sanitizeReasoning(component.evidence),
        rule: sanitizeReasoning(component.rule),
      };
    })
    .filter((row) => row.text || row.score != null)
    // Dedupe identical reasoning within a dimension (the engine sometimes repeats a
    // "TAM not quantified" line across urgency/timing) — repetition reads as padding.
    .filter((row) => {
      const key = row.text.toLowerCase();
      if (!key) return true;
      if (seenText.has(key)) return false;
      seenText.add(key);
      return true;
    })
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
}

export function buildCriterionDrivers(criteria: Record<string, ScoringCriterion>): ScoringDriverRow[] {
  return Object.values(criteria)
    .map((criterion, index) => {
      const text = sanitizeReasoning(criterion.reasoning);
      return {
        id: `criterion-${index}`,
        label: collapseWhitespace(String(criterion.name ?? 'Criterion')),
        tag: null,
        score: typeof criterion.score === 'number' ? criterion.score : null,
        confidence: typeof criterion.confidence === 'number' ? criterion.confidence : null,
        text: text ? clipScoringText(text, 100) : '',
        status: (text ? 'complete' : 'missing') as 'complete' | 'partial' | 'missing',
        missing: !text,
      };
    })
    .filter((row) => row.text || row.score != null)
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
}

export function cleanReasoningList(values: Array<string | null | undefined> | null | undefined): string[] {
  if (!values?.length) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const value of values) {
    const cleaned = sanitizeReasoning(value);
    if (!cleaned) continue;
    const key = cleaned.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(clipScoringText(cleaned, 160));
  }
  return out;
}

export function mergeUniqueBullets(...groups: string[][]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const group of groups) {
    for (const item of group) {
      const key = item.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(item);
    }
  }
  return out;
}
