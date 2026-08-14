import type { Startup } from '../types/startup';

/**
 * Free-text retrieval over the docket.
 *
 * The docket could always acquire a company (⌘K dispatches a lookup) but never
 * retrieve one it already held. This is the retrieval half: name, sector, and
 * one-line, matched as case-insensitive substrings so a half-remembered name
 * finds the row.
 *
 * ponytail: substring match, not fuzzy. A docket is tens-to-hundreds of rows and
 * the operator is recalling a name they have already read. Reach for a scorer
 * only if ranking across thousands of rows becomes the complaint.
 */
export function normalizeQuery(query: string): string {
  return query.trim().toLowerCase();
}

export function startupMatchesQuery(startup: Startup, normalizedQuery: string): boolean {
  if (!normalizedQuery) return true;
  const { name, sector, one_line: oneLine } = startup.scout;
  return [name, sector, oneLine].some(
    (field) => typeof field === 'string' && field.toLowerCase().includes(normalizedQuery),
  );
}
