import type { Startup } from '../types/startup';

export type LookupChipStatus = 'scouting' | 'reviewing' | 'decided';

interface FindTrackedLookupInputs {
  lookupId: string;
  outcomeStartupId?: string;
  isRerun: boolean;
}

/** Resolve a dispatch either by its scout correlation id or by the terminal
 * existing-startup id returned when the company was already in deal flow. */
export function findTrackedLookupStartup(
  startups: Startup[],
  { lookupId, outcomeStartupId, isRerun }: FindTrackedLookupInputs,
): Startup | null {
  const persistedId = outcomeStartupId?.trim();
  if (persistedId) {
    const existing = startups.find((startup) => startup.id === persistedId);
    if (existing) return existing;
  }
  const correlationId = lookupId.trim();
  if (!correlationId) return null;
  return startups.find((startup) => {
    if (!isRerun && (startup.scout.origin_type ?? '').toLowerCase() !== 'on_demand_lookup') {
      return false;
    }
    return (startup.scout.lookup_id ?? '').trim() === correlationId;
  }) ?? null;
}

interface LookupChipStatusInputs {
  isRerun: boolean;
  isActive: boolean;
  lookupDecided: boolean;
  hasPartner: boolean;
  hasReview: boolean;
}

/** A rerun preserves its old review/partner while replacements are generated,
 * so only the live rerun status can call it decided. */
export function lookupChipStatus({
  isRerun,
  isActive,
  lookupDecided,
  hasPartner,
  hasReview,
}: LookupChipStatusInputs): LookupChipStatus {
  if (isRerun) {
    return isActive && lookupDecided ? 'decided' : 'reviewing';
  }
  if (hasPartner) return 'decided';
  if (hasReview) return 'reviewing';
  return 'scouting';
}
