import type { Startup } from '../types/startup';

export type AdverseSeverity = 'high' | 'medium' | 'low';
export type AdverseBasis = 'evidence-backed' | 'inferred';

export interface AdverseRegisterItem {
  id: string;
  severity: AdverseSeverity;
  title: string;
  whyItMatters: string;
  basis: AdverseBasis;
  source?: string;
  missingData?: boolean;
}

const HIGH_TERMS = [
  'red flag',
  'critical',
  'invalidat',
  'fraud',
  'regulator',
  'unverified',
  'no evidence',
  'missing validation',
  'contradiction',
  'adverse',
];

const MEDIUM_TERMS = [
  'risk',
  'unknown',
  'missing',
  'weak',
  'concern',
  'unclear',
  'unresolved',
  'competitive',
  'execution',
];

const MATERIAL_TERMS = [
  ...HIGH_TERMS,
  'customer concentration',
  'no customers',
  'no revenue',
  'churn',
  'regulatory',
  'security',
  'lawsuit',
  'runway',
  'founder',
  'traction',
];

function cleanText(value: unknown): string {
  return String(value ?? '')
    .replace(/^\s*[•·*-]\s+/, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function uniquePush(items: AdverseRegisterItem[], item: AdverseRegisterItem) {
  const key = item.whyItMatters.toLowerCase();
  if (items.some((existing) => existing.whyItMatters.toLowerCase() === key)) return;
  items.push(item);
}

function titleFromText(text: string): string {
  const beforeColon = text.split(':')[0]?.trim();
  const candidate = beforeColon && beforeColon.length <= 76 ? beforeColon : text;
  return candidate
    .replace(/[.!?;:,]+$/g, '')
    .split(' ')
    .slice(0, 8)
    .join(' ');
}

function severityFromText(text: string, fallback: AdverseSeverity = 'medium'): AdverseSeverity {
  const lower = text.toLowerCase();
  if (HIGH_TERMS.some((term) => lower.includes(term))) return 'high';
  if (MEDIUM_TERMS.some((term) => lower.includes(term))) return 'medium';
  return fallback;
}

function isMaterialAdverse(text: string, source: string, severity: AdverseSeverity): boolean {
  const lower = text.toLowerCase();
  if (severity === 'high') return true;
  if (source.includes('red flag') || source.includes('Partner risk') || source.includes('Reviewer risk')) return true;
  return MATERIAL_TERMS.some((term) => lower.includes(term));
}

function basisFromText(text: string, source?: string): AdverseBasis {
  const lower = text.toLowerCase();
  if (source || lower.includes('reference') || lower.includes('reported') || lower.includes('according')) {
    return 'evidence-backed';
  }
  return 'inferred';
}

function addTextItems(
  items: AdverseRegisterItem[],
  values: unknown[] | null | undefined,
  source: string,
  fallbackSeverity: AdverseSeverity
) {
  for (const raw of values ?? []) {
    const text = cleanText(raw);
    if (!text) continue;
    const missingData = /^\[?missing/i.test(text) || text.toLowerCase().includes('missing');
    const severity = severityFromText(text, fallbackSeverity);
    if (!isMaterialAdverse(text, source, severity)) continue;
    uniquePush(items, {
      id: `${source}:${items.length}:${text.slice(0, 28)}`,
      severity,
      title: titleFromText(text),
      whyItMatters: text,
      basis: basisFromText(text, source),
      source,
      missingData,
    });
  }
}

export function extractAdverseRegister(startup: Startup | null | undefined): AdverseRegisterItem[] {
  if (!startup) return [];
  const items: AdverseRegisterItem[] = [];

  addTextItems(items, startup.review?.diligence_red_flags, 'Reviewer red flag', 'high');
  addTextItems(items, startup.review?.key_risks, 'Reviewer risk', 'medium');
  addTextItems(items, startup.partner?.risks, 'Partner risk', 'medium');
  addTextItems(items, startup.review?.assumption_feedback, 'Assumption review', 'medium');
  addTextItems(items, startup.review?.thesis_deviation_points, 'Thesis gap', 'medium');

  for (const review of startup.review?.reviews ?? []) {
    addTextItems(items, review.key_risks, `${review.reviewer_type.replace('Reviewer', '')} review`, 'medium');
  }

  return items.sort((a, b) => {
    const rank: Record<AdverseSeverity, number> = { high: 0, medium: 1, low: 2 };
    return rank[a.severity] - rank[b.severity];
  });
}

export function hasHighSeverityAdverse(startup: Startup | null | undefined): boolean {
  return extractAdverseRegister(startup).some((item) => item.severity === 'high');
}
