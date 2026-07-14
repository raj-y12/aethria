import type { LookupCandidate } from '../api/startups';

const EVIDENCE_LABELS: Record<string, string> = {
  official: 'Official site',
  linkedin: 'LinkedIn',
  crunchbase: 'Crunchbase',
  dealroom: 'Dealroom',
  yc: 'Y Combinator',
  news: 'Press',
};

export function domainLabel(website: string): string {
  return website.replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/\/.*$/, '');
}

export function identityConfidence(confidence: number) {
  const bounded = Math.min(1, Math.max(0, Number.isFinite(confidence) ? confidence : 0));
  const percent = Math.round(bounded * 100);
  if (bounded >= 0.7) return { label: 'Strong identity match', percent, tone: 'strong' as const };
  if (bounded >= 0.4) return { label: 'Likely identity match', percent, tone: 'likely' as const };
  return { label: 'Possible identity match', percent, tone: 'possible' as const };
}

export function evidenceLabels(sourceBadges: string[], hasDomain: boolean): string[] {
  const labels = Array.from(new Set(sourceBadges.map((badge) => EVIDENCE_LABELS[badge.toLowerCase()]).filter(Boolean)));
  return labels.length ? labels : hasDomain ? ['Official domain candidate'] : [];
}

export function isBestIdentityMatch(candidate: LookupCandidate, index: number): boolean {
  return index === 0 && candidate.confidence >= 0.7;
}
