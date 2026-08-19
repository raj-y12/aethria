export function normalizeConfidence(confidence: number | null | undefined): number | null {
  if (typeof confidence !== 'number' || Number.isNaN(confidence)) return null;
  const asFraction = confidence > 1 ? confidence / 100 : confidence;
  return Math.max(0, Math.min(1, asFraction));
}

export function formatConfidencePercent(confidence: number | null | undefined): string {
  const normalized = normalizeConfidence(confidence);
  return normalized == null ? '—' : `${Math.round(normalized * 100)}%`;
}

export function getEvidenceConfidenceLabel(confidence: number | null | undefined): string {
  const normalized = normalizeConfidence(confidence);
  if (normalized == null) return 'Limited';
  if (normalized >= 0.75) return 'Extensive';
  if (normalized >= 0.50) return 'Strong';
  if (normalized >= 0.25) return 'Moderate';
  return 'Limited';
}

export function getEvidenceConfidenceTooltip(confidence: number | null | undefined): string {
  const normalized = normalizeConfidence(confidence);
  if (normalized == null) return 'Evidence quality could not be determined.';
  if (normalized >= 0.75) return 'Multiple independent evidence sources corroborate the assessment.';
  if (normalized >= 0.50) return 'Sufficient evidence is available to support the assessment with reasonable certainty.';
  if (normalized >= 0.25) return 'Some evidence supports the direction but important data points are missing.';
  return 'Limited evidence was available. Key data points remain unverified.';
}

/**
 * Single source of truth for "is this evidence weak enough to flag?" — below the
 * 'Strong' band (i.e. the Limited or Moderate tiers). Replaces ad-hoc per-component
 * thresholds so the low-confidence cue is consistent with the Limited/Moderate/Strong/
 * Extensive vocabulary used everywhere (audit B5 — one confidence treatment).
 */
export function isLowEvidence(confidence: number | null | undefined): boolean {
  const normalized = normalizeConfidence(confidence);
  return normalized != null && normalized < 0.5;
}

