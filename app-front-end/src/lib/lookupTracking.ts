import type { Startup } from '../types/startup';
import type { JobStatus } from '../api/jobs';

type QueryInvalidator = { invalidateQueries: (filters: { queryKey: readonly unknown[] }) => unknown };

export function invalidateLookupCompletionQueries(
  queryClient: QueryInvalidator,
  startupId: string,
  opportunityId?: string | null,
): void {
  void queryClient.invalidateQueries({ queryKey: ['startup', 'detail', startupId] });
  void queryClient.invalidateQueries({ queryKey: ['institutional', 'opportunity', 'legacy', startupId] });
  if (!opportunityId) return;
  void queryClient.invalidateQueries({ queryKey: ['institutional', 'evidence', opportunityId] });
  void queryClient.invalidateQueries({ queryKey: ['institutional', 'evaluation', opportunityId] });
  void queryClient.invalidateQueries({ queryKey: ['institutional', 'rulings', opportunityId] });
}

export function lookupIsWorking(input: {
  busy: boolean; cancelPending: boolean; pending: boolean; autoOpened: boolean;
  decided: boolean; durableStatus?: JobStatus;
}): boolean {
  return input.cancelPending || input.busy || (input.pending && !input.autoOpened
    && !input.decided && input.durableStatus !== 'succeeded');
}

export type LookupChipStatus = 'scouting' | 'reviewing' | 'decided';

interface FindTrackedLookupInputs {
  lookupId: string;
  outcomeStartupId?: string;
  isRerun: boolean;
  /** The existing row a re-review targets, recorded when it was dispatched. */
  targetStartupId?: string;
}

/** Resolve a dispatch to its startup row.
 *
 * Order matters. A re-review's target is known the moment it is dispatched, so
 * it resolves immediately and stays resolvable even if the backend never stamps
 * the new correlation id onto that row. Matching on the correlation id alone
 * left re-reviews unresolved — and an unresolved dispatch never polls its memo
 * status, so it could never be marked done, cleared, or opened.
 */
export function findTrackedLookupStartup(
  startups: Startup[],
  { lookupId, outcomeStartupId, isRerun, targetStartupId }: FindTrackedLookupInputs,
): Startup | null {
  const target = targetStartupId?.trim();
  if (target) {
    const existing = startups.find((startup) => startup.id === target);
    if (existing) return existing;
  }
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

interface RerunSettledInputs {
  startup: Startup | null;
  /** When the re-review was accepted by the backend. */
  acceptedAt?: string;
}

/** Whether a re-review has produced fresh downstream output.
 *
 * A re-review keeps its previous review/partner while replacements generate, so
 * their mere presence proves nothing — only a timestamp newer than the dispatch
 * does. Without an accepted-at there is no way to tell old output from new, so
 * this reports false rather than guessing.
 */
export function rerunHasSettled({ startup, acceptedAt }: RerunSettledInputs): boolean {
  if (!startup || !acceptedAt) return false;
  const dispatchedAt = Date.parse(acceptedAt);
  if (!Number.isFinite(dispatchedAt)) return false;
  return [startup.timestamps?.partnered_at, startup.timestamps?.reviewed_at].some((value) => {
    if (!value) return false;
    const at = Date.parse(value);
    return Number.isFinite(at) && at >= dispatchedAt;
  });
}

interface LookupChipStatusInputs {
  isRerun: boolean;
  isActive: boolean;
  lookupDecided: boolean;
  hasPartner: boolean;
  hasReview: boolean;
  /** For a backgrounded re-review, whether fresh output has landed. */
  rerunSettled?: boolean;
}

/** A rerun preserves its old review/partner while replacements are generated,
 * so only live status (active) or a post-dispatch timestamp (backgrounded) can
 * call it decided. */
export function lookupChipStatus({
  isRerun,
  isActive,
  lookupDecided,
  hasPartner,
  hasReview,
  rerunSettled = false,
}: LookupChipStatusInputs): LookupChipStatus {
  if (isRerun) {
    if (isActive) return lookupDecided ? 'decided' : 'reviewing';
    // A backgrounded re-review has no live poll behind it. Without this it could
    // never leave 'reviewing' and sat on the rail as a permanently in-flight chip.
    return rerunSettled ? 'decided' : 'reviewing';
  }
  if (hasPartner) return 'decided';
  if (hasReview) return 'reviewing';
  return 'scouting';
}
