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

function boundedConfidence(value: number): number {
  return Math.min(1, Math.max(0, Number.isFinite(value) ? value : 0));
}

/** Resolver confidence as analyst-facing language — tiers only, no false precision. */
export function identityConfidence(confidence: number): string {
  const bounded = boundedConfidence(confidence);
  if (bounded >= 0.7) return 'Strong identity match';
  if (bounded >= 0.4) return 'Likely identity match';
  return 'Possible identity match';
}

/** Only real verification sources — a bare domain is not evidence. */
export function evidenceLabels(sourceBadges: string[]): string[] {
  return Array.from(new Set(sourceBadges.map((badge) => EVIDENCE_LABELS[badge.toLowerCase()]).filter(Boolean)));
}

// ponytail: the resolver returns candidates sorted by confidence desc, so best
// match is simply a strong first row — no scan needed.
export function isBestIdentityMatch(candidate: LookupCandidate, index: number): boolean {
  return index === 0 && boundedConfidence(candidate.confidence) >= 0.7;
}
