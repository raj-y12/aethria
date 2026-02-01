interface DividerProps {
  /** Full width (default) or constrained to content. */
  fullWidth?: boolean;
  className?: string;
}

/**
 * Soft horizontal line. Structural rhythm, not decorative.
 * Uses charcoal/10 — subtle, institutional.
 */
export default function Divider({
  fullWidth = true,
  className = '',
}: DividerProps) {
  const w = fullWidth ? 'w-full' : 'w-full max-w-[80%] mx-auto';
  return (
    <div
      role="separator"
      aria-hidden="true"
      className={`h-px bg-oxford/[0.08] ${w} ${className}`}
    />
  );
}
