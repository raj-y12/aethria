/**
 * Verdict tint — colour-tinted, not colour-coded.
 *
 * One dimension: text colour. Layout does the heavy lifting.
 * PASS = quietest. WATCH/MAYBE = muted. YES/NO = deeper contrast.
 * onDark: for oxford background — white at opacity (matches SystemBar / verdict bar).
 */
type PartnerDecision = 'YES' | 'NO' | 'MAYBE' | 'PASS' | 'WATCH';

/** Tailwind text colour class for verdict label. onDark = light text on oxford. */
export function verdictTextClass(decision: PartnerDecision, onDark = false): string {
  if (onDark) {
    switch (decision) {
      case 'PASS':
        return 'text-white/50';
      case 'WATCH':
      case 'MAYBE':
        return 'text-white/70';
      case 'YES':
      case 'NO':
        return 'text-white/90';
      default:
        return 'text-white/70';
    }
  }
  switch (decision) {
    case 'PASS':
      return 'text-oxford/60';
    case 'WATCH':
    case 'MAYBE':
      return 'text-oxford/60';
    case 'YES':
    case 'NO':
      return 'text-oxford/80';
    default:
      return 'text-oxford/60';
  }
}
