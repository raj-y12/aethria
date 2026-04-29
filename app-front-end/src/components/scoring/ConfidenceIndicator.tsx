interface ConfidenceIndicatorProps {
  confidence: number | null | undefined;
}

function getConfidenceTone(confidence: number | null | undefined): {
  label: string;
  width: string;
} {
  if (typeof confidence !== 'number' || Number.isNaN(confidence)) {
    return { label: 'Unknown confidence', width: '0%' };
  }
  const clamped = Math.max(0, Math.min(1, confidence));
  if (clamped >= 0.75) return { label: 'High confidence', width: `${clamped * 100}%` };
  if (clamped >= 0.45) return { label: 'Medium confidence', width: `${clamped * 100}%` };
  return { label: 'Low confidence', width: `${clamped * 100}%` };
}

export default function ConfidenceIndicator({ confidence }: ConfidenceIndicatorProps) {
  const tone = getConfidenceTone(confidence);
  return (
    <div className="mt-1.5" title={`${tone.label}${typeof confidence === 'number' ? ` · ${Math.round(confidence * 100)}%` : ''}`}>
      <div className="relative h-[1px] w-full overflow-hidden bg-oxford/10">
        <div className="absolute inset-0 h-full origin-left bg-oxford/40" style={{ width: tone.width }} />
      </div>
    </div>
  );
}
