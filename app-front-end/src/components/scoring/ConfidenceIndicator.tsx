interface ConfidenceIndicatorProps {
  confidence: number | null | undefined;
}

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

function getConfidenceTone(confidence: number | null | undefined): {
  label: string;
  width: string;
} {
  const normalized = normalizeConfidence(confidence);
  if (normalized == null) {
    return { label: 'Limited', width: '0%' };
  }
  const width = `${normalized * 100}%`;
  if (normalized >= 0.75) return { label: 'Extensive', width };
  if (normalized >= 0.50) return { label: 'Strong', width };
  if (normalized >= 0.25) return { label: 'Moderate', width };
  return { label: 'Limited', width };
}

export default function ConfidenceIndicator({ confidence }: ConfidenceIndicatorProps) {
  const tone = getConfidenceTone(confidence);
  const tooltip = getEvidenceConfidenceTooltip(confidence);
  return (
    <div className="mt-1.5" title={`Evidence: ${tone.label} · ${tooltip}`}>
      <div className="h-[2px] w-full overflow-hidden bg-oxford/10">
        <div className="h-full bg-oxford/45" style={{ width: tone.width }} />
      </div>
    </div>
  );
}
