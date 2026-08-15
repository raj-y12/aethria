import type { CompanyResolution, FounderCandidate, FounderResolution } from '../types/startup';

/** Founder Resolver `missing_fields` -> reader-facing labels. */
export const FOUNDER_MISSING_FIELD_LABELS: Record<string, string> = {
  role: 'role',
  linkedin_url: 'LinkedIn profile',
  x_url: 'X profile',
  github_url: 'GitHub profile',
  previous_employment: 'previous employment',
  education: 'education',
};

export interface FounderSectionModel {
  /** Structured founders, when the Founder Resolver produced them. */
  candidates: FounderCandidate[];
  /** Names to show when there is no structured detail (older rows, resolver output). */
  names: string[];
  /** Founder fields the resolver looked for and could not confirm. */
  missing: string[];
  /**
   * Message to show instead of names. Null when there is something to show.
   * Distinguishes "we searched and found nobody" from "we never looked".
   */
  emptyMessage: string | null;
}

interface FounderSectionInput {
  founderResolution?: FounderResolution | null;
  companyResolution?: CompanyResolution | null;
  scoutFounderNames?: string[] | null;
}

const NOT_FOUND_MESSAGE =
  'No founder could be confirmed from the sources retrieved for this company.';
const NOT_GATHERED_MESSAGE = 'Founder details have not been gathered for this company yet.';

function normalizedCompanyName(value: string | null | undefined): string {
  return String(value ?? '')
    .trim()
    .toLocaleLowerCase()
    .replace(/[^a-z0-9]+/g, '');
}

function cleanedFounderName(value: string | null | undefined): string {
  return String(value ?? '')
    .trim()
    .replace(/_+$/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function cleanFounderNames(values: Array<string | null | undefined>): string[] {
  const cleaned = values.map(cleanedFounderName).filter(Boolean);
  const normalized = new Set(cleaned.map(normalizedCompanyName));
  const seen = new Set<string>();
  return cleaned.filter((name) => {
    const key = normalizedCompanyName(name);
    const navigationTarget = name.match(/^meet\s+(.+)$/i)?.[1];
    if (navigationTarget && normalized.has(normalizedCompanyName(navigationTarget))) return false;
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function completeResolverMatchesCompany(
  founderResolution: FounderResolution | null | undefined,
  companyResolution: CompanyResolution | null | undefined,
): boolean {
  if (founderResolution?.resolution_status?.trim().toUpperCase() !== 'FOUND') return false;
  if ((founderResolution.missing_fields?.length ?? 0) > 0) return false;
  if (!companyResolution) return true;

  const resolvedCompany = normalizedCompanyName(founderResolution.company);
  return Boolean(resolvedCompany) && (
    resolvedCompany === normalizedCompanyName(companyResolution.canonical_name)
    || resolvedCompany === normalizedCompanyName(companyResolution.query)
  );
}

/**
 * Derive what the memo's Founder section should show.
 *
 * The section always renders: a memo that silently omits founders reads as
 * "no team risk" when it actually means "we could not find them", which is a
 * materially different thing for an investment decision.
 */
export function buildFounderSectionModel({
  founderResolution,
  companyResolution,
  scoutFounderNames,
}: FounderSectionInput): FounderSectionModel {
  const scoutNames = cleanFounderNames(scoutFounderNames ?? []);
  const resolverCandidateNames = cleanFounderNames(
    (founderResolution?.founders ?? []).map((founder) => founder?.name),
  );
  const resolverCandidateNameSet = new Set(resolverCandidateNames.map(normalizedCompanyName));
  const resolverCandidates = (founderResolution?.founders ?? [])
    .map((founder) => ({ ...founder, name: cleanedFounderName(founder?.name) }))
    .filter((founder, index, candidates) => {
      const key = normalizedCompanyName(founder.name);
      if (!key || !resolverCandidateNameSet.has(key)) return false;
      return candidates.findIndex((candidate) => normalizedCompanyName(candidate.name) === key) === index;
    });
  const candidates = scoutNames.length > 0 && !completeResolverMatchesCompany(founderResolution, companyResolution)
    ? []
    : resolverCandidates;

  const names = candidates.length
    ? candidates.map((f) => f.name)
    : scoutNames.length
      ? scoutNames
      : companyResolution?.founder_names?.length
      ? cleanFounderNames(companyResolution.founder_names)
      : [];

  // `founder_names` is reported as missing when nobody was found at all; the
  // section already says that in prose, so it is not repeated as a field.
  const missing = (founderResolution?.missing_fields ?? []).filter(
    (f) => f !== 'founder_names',
  );

  let emptyMessage: string | null = null;
  if (names.length === 0) {
    emptyMessage = founderResolution ? NOT_FOUND_MESSAGE : NOT_GATHERED_MESSAGE;
  }

  return { candidates, names, missing, emptyMessage };
}

export function formatFounderBackground(founder: FounderCandidate): string {
  return [
    founder.previous_employment?.length
      ? `Previously ${founder.previous_employment.join(', ')}`
      : null,
    founder.education?.length ? founder.education.join(', ') : null,
  ]
    .filter(Boolean)
    .join(' · ');
}

export function formatMissingFounderFields(missing: string[]): string {
  return missing
    .map((f) => FOUNDER_MISSING_FIELD_LABELS[f] ?? f.replace(/_/g, ' '))
    .join(', ');
}
