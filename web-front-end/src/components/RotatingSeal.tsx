import { useId } from 'react';

/**
 * Rotating circular seal — the page's signature mark (à la Seedcamp's rotating badge).
 * Mono caps running around a ring, a fine inner hairline, and a centered mark.
 * Oxford ink on paper; verdigris center. Rotation pauses for reduced-motion.
 */
export interface RotatingSealProps {
  /** Text that runs around the ring. A trailing separator is appended automatically. */
  label?: string;
  /** Diameter in px (the SVG is responsive via className width). */
  className?: string;
}

const DEFAULT_LABEL = 'AETHRIA · PRIVATE MARKET JUDGMENT · MADE INSPECTABLE · ';

export default function RotatingSeal({ label = DEFAULT_LABEL, className }: RotatingSealProps) {
  const id = useId().replace(/[:]/g, '');
  const pathId = `seal-path-${id}`;
  // Ring path: a circle drawn as two arcs so textPath wraps cleanly.
  const r = 86;
  const cx = 100;
  const cy = 100;

  return (
    <div className={className} aria-hidden>
      <svg viewBox="0 0 200 200" className="seal-spin h-full w-full">
        <defs>
          <path id={pathId} d={`M ${cx} ${cy} m -${r},0 a ${r},${r} 0 1,1 ${r * 2},0 a ${r},${r} 0 1,1 -${r * 2},0`} />
        </defs>

        {/* outer + inner hairlines */}
        <circle cx={cx} cy={cy} r={97} fill="none" stroke="rgba(0,20,51,0.16)" strokeWidth="1" />
        <circle cx={cx} cy={cy} r={70} fill="none" stroke="rgba(0,20,51,0.12)" strokeWidth="1" />

        {/* running text */}
        <text fontFamily="var(--font-mono)" fontSize="9.5" letterSpacing="3.1" fill="rgba(0,20,51,0.62)">
          <textPath href={`#${pathId}`} startOffset="0">
            {label}
          </textPath>
        </text>

        {/* center mark — verdigris diamond + serif monogram */}
        <g>
          <rect x={cx - 4} y={cy - 26} width="8" height="8" transform={`rotate(45 ${cx} ${cy - 22})`} fill="var(--color-accent)" />
          <text
            x={cx}
            y={cy + 12}
            textAnchor="middle"
            fontFamily="var(--font-display)"
            fontSize="34"
            fontWeight="500"
            fill="var(--color-oxford)"
          >
            Æ
          </text>
        </g>
      </svg>
    </div>
  );
}
