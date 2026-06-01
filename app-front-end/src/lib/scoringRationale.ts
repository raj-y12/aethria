import { getScoreBand } from '../design-system/semantics';
import type { PresentationDimension, ScoringComponent, ScoringCriterion, ScoringDimension } from '../types/startup';
import { sanitizeReasoning } from './reviewScoring';

function collapseWhitespace(value: string): string {
  return value.replace(/\s+/g, ' ').trim();
}

export function clipScoringText(value: string, max = 96): string {
  const text = collapseWhitespace(value);
  if (text.length <= max) return text;
  const cutoff = text.lastIndexOf(' ', max - 1);
  return `${text.slice(0, cutoff > 32 ? cutoff : max - 1).trim()}…`;
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
  label: string;
  score: number | null;
  text: string;
  missing: boolean;
};

export function buildComponentDrivers(components: Record<string, ScoringComponent>): ScoringDriverRow[] {
  return Object.entries(components)
    .map(([id, component]) => {
      const text = sanitizeReasoning(component.reasoning) ?? sanitizeReasoning(component.evidence);
      const label = collapseWhitespace(String(component.label ?? id.replace(/_/g, ' ')));
      const missing = !text && (component.score == null || component.score <= 0);
      return {
        id,
        label,
        score: typeof component.score === 'number' ? component.score : null,
        text: text ? clipScoringText(text, 100) : '',
        missing,
      };
    })
    .filter((row) => row.text || row.score != null)
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
}

export function buildCriterionDrivers(criteria: Record<string, ScoringCriterion>): ScoringDriverRow[] {
  return Object.values(criteria)
    .map((criterion, index) => {
      const text = sanitizeReasoning(criterion.reasoning);
      return {
        id: `criterion-${index}`,
        label: collapseWhitespace(String(criterion.name ?? 'Criterion')),
        score: typeof criterion.score === 'number' ? criterion.score : null,
        text: text ? clipScoringText(text, 100) : '',
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
