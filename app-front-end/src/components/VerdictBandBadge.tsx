import type { ReviewerQualityBand } from '../design-system/semantics';

/** Same footprint as `DecisionBadge` (type-label-tab, py-1 px-2). */
const PILL_BASE =
  'inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none type-label-tab py-1 px-2 uppercase shadow-none';

const TONE: Record<ReviewerQualityBand, string> = {
  STRONG: 'bg-oxford text-paper',
  MEDIUM: 'bg-oxford/50 text-paper',
  WEAK: 'bg-oxford/20 text-oxford',
};

export default function VerdictBandBadge({ band }: { band: ReviewerQualityBand }) {
  return (
    <span className={`${PILL_BASE} ${TONE[band]}`} aria-label={band}>
      {band}
    </span>
  );
}
