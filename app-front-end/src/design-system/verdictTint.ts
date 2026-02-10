/**
 * Verdict tint — colour-tinted, not colour-coded.
 *
 * One dimension: text colour. Layout does the heavy lifting.
 * PASS = quietest. WATCH/MAYBE = bone/muted. YES/NO = deeper contrast.
 * onDark: for oxford background — ivory text opacities (matches SystemBar / verdict bar).
 */
type PartnerDecision = 'YES' | 'NO' | 'MAYBE' | 'PASS' | 'WATCH';

/** Tailwind text colour class for verdict label. onDark = light text on oxford. */
export function verdictTextClass(decision: PartnerDecision, onDark = false): string {
  if (onDark) {
    switch (decision) {
      case 'PASS':
        return 'text-ivory/50';
      case 'WATCH':
      case 'MAYBE':
        return 'text-ivory/70';
      case 'YES':
      case 'NO':
        return 'text-ivory/90';
      default:
        return 'text-ivory/70';
    }
  }
  switch (decision) {
    case 'PASS':
      return 'text-oxford/50';
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
