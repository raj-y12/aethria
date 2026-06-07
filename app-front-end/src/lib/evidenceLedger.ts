/**
 * Evidence ledger — promotes provenance to a first-class, auditable view.
 *
 * Built ENTIRELY from signals the pipeline already captures. We do not fabricate
 * source dates or quality scores the system doesn't record:
 *  - claim-level citations  ← scout.source_evidence[].supports
 *  - verified vs inferred    ← scout.field_provenance (reviewer_text_infer = inferred)
 *  - primary vs secondary    ← URL host vs the company's own domain
 *  - missing evidence (gaps) ← caller passes the already-computed list
 *  - contested signal        ← reviewer disagreement
 */
import type { Startup } from '../types/startup';

// Quality tier of a cited source, derived deterministically from its domain.
//  - official:  the company's own site (primary, first-party)
//  - reputable: curated credible third parties (major press, registries, filings)
//  - web:       any other resolvable third-party host
//  - unknown:   no usable URL
export type EvidenceSourceType = 'official' | 'reputable' | 'web' | 'unknown';

export interface EvidenceLedgerEntry {
  claim: string;
  label: string;
  href?: string;
  sourceType: EvidenceSourceType;
}

export interface EvidenceLedgerModel {
  entries: EvidenceLedgerEntry[];
  /** Count of cited sources per quality tier. */
  tierCounts: Record<EvidenceSourceType, number>;
  /** Fields the reviewer inferred from prose rather than sourcing (lower trust). */
  inferredFields: string[];
  /** Fields backed by scout discovery, extraction, or gap retrieval. */
  sourcedFieldCount: number;
  missingEvidence: string[];
  contested: boolean;
}

// Curated registrable domains treated as reputable third parties. Conservative
// on purpose — better to under-claim quality than overstate it on a trust surface.
const REPUTABLE_DOMAINS = new Set([
  'techcrunch.com', 'reuters.com', 'bloomberg.com', 'forbes.com', 'wsj.com', 'ft.com',
  'nytimes.com', 'theinformation.com', 'axios.com', 'theverge.com', 'venturebeat.com',
  'businesswire.com', 'prnewswire.com', 'crunchbase.com', 'pitchbook.com', 'cbinsights.com',
  'sifted.eu', 'techeu.com', 'github.com', 'producthunt.com', 'sec.gov', 'gov.uk',
]);

function registrableDomain(host: string): string {
  const parts = host.split('.');
  return parts.length <= 2 ? host : parts.slice(-2).join('.');
}

function isReputable(host: string): boolean {
  const reg = registrableDomain(host);
  if (REPUTABLE_DOMAINS.has(reg)) return true;
  // Public-sector / academic TLDs read as reputable.
  return /\.(gov|edu|gov\.[a-z]{2}|ac\.[a-z]{2})$/.test(host);
}

type SourceRow = { reference: string; supports: string; href?: string | null; label: string };

function hostOf(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url.includes('://') ? url : `https://${url}`);
    return u.hostname.replace(/^www\./, '').toLowerCase();
  } catch {
    return null;
  }
}

function companyHost(startup: Startup): string | null {
  // Prefer an explicit lookup website; otherwise infer from the company name token.
  const fromWebsite = hostOf(startup.scout.lookup_website);
  if (fromWebsite) return fromWebsite;
  const name = (startup.scout.name || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  return name ? name : null;
}

function classify(host: string | null, company: string | null): EvidenceSourceType {
  if (!host) return 'unknown';
  // Company's own domain (or a domain containing the company token) reads as first-party.
  if (company && (host === company || host.split('.')[0] === company || host.includes(company))) {
    return 'official';
  }
  if (isReputable(host)) return 'reputable';
  return 'web';
}

const SOURCED_PROVENANCE = new Set(['scout', 'reviewer_extraction', 'gap_retrieval']);

export function buildEvidenceLedger(
  startup: Startup,
  sources: SourceRow[],
  missingEvidence: string[]
): EvidenceLedgerModel {
  const company = companyHost(startup);

  const entries: EvidenceLedgerEntry[] = sources.map((s) => ({
    claim: s.supports || 'Company evidence',
    label: s.label,
    href: s.href ?? undefined,
    sourceType: classify(hostOf(s.href), company),
  }));

  const tierCounts: Record<EvidenceSourceType, number> = { official: 0, reputable: 0, web: 0, unknown: 0 };
  for (const e of entries) tierCounts[e.sourceType] += 1;

  const provenance: Record<string, string> = startup.scout.field_provenance ?? {};
  const inferredFields: string[] = [];
  let sourcedFieldCount = 0;
  for (const [field, prov] of Object.entries(provenance)) {
    if (prov === 'reviewer_text_infer') inferredFields.push(field);
    else if (SOURCED_PROVENANCE.has(prov)) sourcedFieldCount += 1;
  }

  const contested = Boolean(
    startup.review?.reviewer_disagreement ||
      startup.partner?.llm_fallback_reason?.toLowerCase().includes('disagree')
  );

  return {
    entries,
    tierCounts,
    inferredFields,
    sourcedFieldCount,
    missingEvidence,
    contested,
  };
}

/** True when there is anything worth showing in the ledger. */
export function hasEvidence(model: EvidenceLedgerModel): boolean {
  return (
    model.entries.length > 0 ||
    model.missingEvidence.length > 0 ||
    model.inferredFields.length > 0 ||
    model.sourcedFieldCount > 0
  );
}

/** Human-readable field label (snake_case → Title Case). */
export function prettyFieldName(field: string): string {
  return field
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}
