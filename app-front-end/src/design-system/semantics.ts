/**
 * Shared semantics for scores, verdicts, and decisions.
 * Align with resources/rubrics/evaluation_rubric_v1.json (v1.1)
 * and resources/partner_rules.json.
 */

/** Score band: human-readable meaning of a 1–10 score. v1.1 rubric. */
export const SCORE_BANDS = [
  { range: [1, 3] as [number, number], label: 'Weak', meaning: 'High risk, failing, or structurally broken' },
  { range: [4, 5] as [number, number], label: 'Concerning', meaning: 'Unproven, material execution or validation gaps' },
  { range: [6, 7] as [number, number], label: 'Promising', meaning: 'Reasonable thesis, requires validation' },
  { range: [8, 10] as [number, number], label: 'Strong', meaning: 'Investment-grade, clear upside with managed risk' },
] as const;

export function getScoreBand(score: number): { label: string; meaning: string } {
  for (const band of SCORE_BANDS) {
    if (score >= band.range[0] && score <= band.range[1]) {
      return { label: band.label, meaning: band.meaning };
    }
  }
  return { label: '—', meaning: '' };
}

/** Quality assessment from Reviewer (STRONG/MEDIUM/WEAK). */
export const QUALITY_LABELS: Record<string, string> = {
  STRONG: 'Investment-grade',
  MEDIUM: 'Promising but incomplete',
  WEAK: 'Insufficient quality',
};

/** Investment decision from Partner (YES/NO/MAYBE). Legacy PASS/WATCH map for compatibility. */
export const DECISION_LABELS: Record<string, string> = {
  YES: 'Advance',
  NO: 'Pass',
  MAYBE: 'Hold',
  PASS: 'Pass',
  WATCH: 'Hold',
};

/** Dimension display order: primary drivers first, then supporting. */
export const SCORE_DIMENSIONS = [
  { id: 'market_score', name: 'Market' },
  { id: 'execution_score', name: 'Execution' },
  { id: 'product_score', name: 'Product' },
  { id: 'technical_score', name: 'Technical' },
  { id: 'defensibility_score', name: 'Defensibility' },
] as const;
