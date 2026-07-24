import { usePrefersReducedMotion } from '../hooks';

interface LoadingAnimationProps {
  fullScreen?: boolean;
}

/**
 * System calibration — Compact Triangle Dot Grid Matrix.
 * 15 circular dots (4px) arranged in a compact 5-row triangle matrix.
 * 0.1 → 1 → 0.1 organic staggered pulse between Oxford Blue (#0a1629) and Verdigris Green (#3d6b5e).
 * Zero grey tones. Respects prefers-reduced-motion.
 */
export default function LoadingAnimation({
  fullScreen = true,
}: LoadingAnimationProps) {
  const reduceMotion = usePrefersReducedMotion();

  const containerClass = fullScreen
    ? 'fixed inset-0 min-h-[100dvh] bg-paper z-[200] flex flex-col items-center justify-center overflow-hidden'
    : 'flex flex-col items-center justify-center min-h-[200px] py-12 overflow-hidden bg-paper';

  return (
    <div className={containerClass}>
      <div className={`aethria-triangle-dot-grid${reduceMotion ? ' aethria-dot-grid--static' : ''}`}>
        {/* Row 1: 1 dot */}
        <div className="aethria-grid-row">
          <div className="aethria-t-dot r1d1" />
        </div>
        {/* Row 2: 2 dots */}
        <div className="aethria-grid-row">
          <div className="aethria-t-dot r2d1" />
          <div className="aethria-t-dot r2d2" />
        </div>
        {/* Row 3: 3 dots */}
        <div className="aethria-grid-row">
          <div className="aethria-t-dot r3d1" />
          <div className="aethria-t-dot r3d2" />
          <div className="aethria-t-dot r3d3" />
        </div>
        {/* Row 4: 4 dots */}
        <div className="aethria-grid-row">
          <div className="aethria-t-dot r4d1" />
          <div className="aethria-t-dot r4d2" />
          <div className="aethria-t-dot r4d3" />
          <div className="aethria-t-dot r4d4" />
        </div>
        {/* Row 5: 5 dots */}
        <div className="aethria-grid-row">
          <div className="aethria-t-dot r5d1" />
          <div className="aethria-t-dot r5d2" />
          <div className="aethria-t-dot r5d3" />
          <div className="aethria-t-dot r5d4" />
          <div className="aethria-t-dot r5d5" />
        </div>
      </div>
    </div>
  );
}
