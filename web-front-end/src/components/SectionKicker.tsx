/**
 * Folio kicker — the quiet editorial label that opens every section (folio number,
 * a short hairline, a mono caption). Repeating it page-wide turns the sections into
 * one numbered document. Matches the hero's "01 — The thesis engine".
 */
export interface SectionKickerProps {
  folio: string;
  label: string;
  /** On dark surfaces, lighten the ink. */
  inverse?: boolean;
  className?: string;
}

export default function SectionKicker({ folio, label, inverse = false, className }: SectionKickerProps) {
  const muted = inverse ? 'text-[var(--text-inverse-muted)]' : 'text-[var(--label-muted)]';
  const rule = inverse ? 'bg-[rgba(244,241,234,0.22)]' : 'bg-[var(--section-divider)]';

  return (
    <div className={`flex items-center gap-4 ${className ?? ''}`}>
      <span className={`font-mono text-[11px] tracking-[0.14em] ${muted}`}>{folio}</span>
      <span className={`h-px w-10 shrink-0 ${rule}`} />
      <span className={`font-mono text-[10px] uppercase tracking-[0.18em] ${muted}`}>{label}</span>
    </div>
  );
}
