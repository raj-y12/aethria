/**
 * `partner.decision_drivers` are machine tags, not prose.
 *
 * The backend emits a stable tag list (`backend/partner/rationale.py`,
 * TAG_PRIORITY) so decisions stay analysable. Several memo surfaces spliced
 * that list straight into human-readable copy, which rendered "critical_risk"
 * as a bullet in the memo's Why Now section.
 *
 * Tags are a contract: add here when a new one is added to TAG_PRIORITY. An
 * unknown tag is de-slugged rather than dropped, so a new backend tag degrades
 * to readable text instead of vanishing.
 */
const DECISION_DRIVER_LABELS: Record<string, string> = {
  critical_risk: 'A critical risk blocks the recommendation',
  weak_verdict: 'Reviewers reached a weak verdict',
  below_pass_threshold: 'Scores fall below the pass threshold',
  contradictory_scores: 'Dimension scores contradict each other',
  reviewer_disagreement: 'Reviewers disagree materially',
  missing_qualitative: 'Critical qualitative evidence is missing',
  grey_zone: 'Scores sit in the policy grey zone',
  borderline_medium: 'A borderline medium call',
  strong_below_yes_bar: 'Strong, but below the commit bar',
  medium_watch_high: 'Medium with high watch priority',
  strong_commit: 'Scores clear the commit bar',
  default_pass: 'No decisive driver was recorded',
  insufficient_evidence_coverage: 'Evidence coverage is insufficient to decide',
  thesis_mismatch: 'The company sits outside the mandate',
};

/** True when the value looks like a machine tag rather than a written sentence. */
export function isDecisionDriverTag(value: string): boolean {
  const text = value.trim();
  if (!text) return false;
  return text in DECISION_DRIVER_LABELS || /^[a-z][a-z0-9]*(_[a-z0-9]+)+$/.test(text);
}

/** Render a driver for human display; passes prose through untouched. */
export function formatDecisionDriver(value: string): string {
  const text = value.trim();
  if (!text) return '';
  const known = DECISION_DRIVER_LABELS[text];
  if (known) return known;
  if (isDecisionDriverTag(text)) {
    const words = text.replace(/_/g, ' ');
    return words.charAt(0).toUpperCase() + words.slice(1);
  }
  return text;
}

export function formatDecisionDrivers(values: string[] | undefined): string[] {
  return (values ?? []).map(formatDecisionDriver).filter(Boolean);
}
