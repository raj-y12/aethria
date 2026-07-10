export type LookupChipStatus = 'scouting' | 'reviewing' | 'decided';

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
