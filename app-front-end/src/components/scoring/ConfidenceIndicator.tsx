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

function getConfidenceTone(confidence: number | null | undefined): {
  label: string;
  width: string;
} {
  const normalized = normalizeConfidence(confidence);
  if (normalized == null) {
    return { label: 'Unknown confidence', width: '0%' };
  }
  const width = `${normalized * 100}%`;
  if (normalized >= 0.75) return { label: 'High confidence', width };
  if (normalized >= 0.45) return { label: 'Medium confidence', width };
  return { label: 'Low confidence', width };
}

export default function ConfidenceIndicator({ confidence }: ConfidenceIndicatorProps) {
  const tone = getConfidenceTone(confidence);
  return (
    <div className="mt-1.5" title={`${tone.label} · ${formatConfidencePercent(confidence)}`}>
      <div className="h-[2px] w-full overflow-hidden bg-oxford/10">
        <div className="h-full bg-oxford/45" style={{ width: tone.width }} />
      </div>
    </div>
  );
}
