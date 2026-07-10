/**
 * Verdict tint — colour-tinted, not colour-coded.
 *
 * One dimension: text colour. Layout does the heavy lifting.
 * PASS = quietest. MONITOR = muted. INVEST = deeper contrast.
 * onDark: for oxford background — white at opacity (matches SystemBar / verdict bar).
 */
type PartnerDecision = 'INVEST' | 'PASS' | 'MONITOR';

/** Tailwind text colour class for verdict label. onDark = light text on oxford. */
export function verdictTextClass(decision: PartnerDecision, onDark = false): string {
  if (onDark) {
    switch (decision) {
      case 'PASS':
        return 'text-white/60';
      case 'MONITOR':
        return 'text-white/70';
      case 'INVEST':
        return 'text-white/90';
      default:
        return 'text-white/70';
    }
  }
  switch (decision) {
    case 'PASS':
      return 'text-oxford/60';
    case 'MONITOR':
      return 'text-oxford/60';
    case 'INVEST':
      return 'text-oxford/80';
    default:
      return 'text-oxford/60';
  }
}
