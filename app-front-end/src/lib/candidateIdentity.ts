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
  const value = website.trim();
  if (!value) return '';
  try {
    const parsed = new URL(/^[a-z][a-z\d+.-]*:\/\//i.test(value) ? value : `https://${value}`);
    const hostname = parsed.hostname.toLowerCase().replace(/^www\./, '');
    if (!hostname || (!hostname.includes('.') && !/^\d{1,3}(?:\.\d{1,3}){3}$/.test(hostname))) return '';
    return hostname;
  } catch {
    return '';
  }
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

export function isBestIdentityMatch(candidate: LookupCandidate, index: number, candidates?: LookupCandidate[]): boolean {
  const confidence = (value: number) => Math.min(1, Math.max(0, Number.isFinite(value) ? value : 0));
  if (!candidates) return index === 0 && confidence(candidate.confidence) >= 0.7;
  const strongest = Math.max(...candidates.map((entry) => confidence(entry.confidence)), 0);
  const firstStrongestIndex = candidates.findIndex((entry) => confidence(entry.confidence) === strongest);
  return index === firstStrongestIndex && strongest >= 0.7 && confidence(candidate.confidence) === strongest;
}

export function candidateIdentityKey(candidate: LookupCandidate, candidates: LookupCandidate[], index: number): string {
  const signature = [
    candidate.name.trim().toLowerCase(),
    domainLabel(candidate.website),
    [...candidate.source_badges].sort().join(','),
    Number.isFinite(candidate.confidence) ? candidate.confidence : 0,
  ].join('|');
  const occurrence = candidates.slice(0, index).filter((entry) => {
    const entrySignature = [
      entry.name.trim().toLowerCase(),
      domainLabel(entry.website),
      [...entry.source_badges].sort().join(','),
      Number.isFinite(entry.confidence) ? entry.confidence : 0,
    ].join('|');
    return entrySignature === signature;
  }).length;
  return `${signature}-${occurrence}`;
}
