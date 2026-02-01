/**
 * Verdict tint — colour-tinted, not colour-coded.
 *
 * One dimension: text colour. Layout does the heavy lifting.
 * PASS = quietest. WATCH/MAYBE = bone/muted. YES/NO = deeper contrast.
 */
type PartnerDecision = 'YES' | 'NO' | 'MAYBE' | 'PASS' | 'WATCH';

/** Tailwind text colour class for verdict label. Single signal. */
export function verdictTextClass(decision: PartnerDecision): string {
  switch (decision) {
    case 'PASS':
      return 'text-charcoal/45'; // quietest — "of course this was filtered"
    case 'WATCH':
    case 'MAYBE':
      return 'text-charcoal/55'; // bone / muted
    case 'YES':
    case 'NO':
      return 'text-charcoal/75'; // deeper contrast, restrained
    default:
      return 'text-charcoal/55';
  }
}
