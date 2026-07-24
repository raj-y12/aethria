import { usePrefersReducedMotion } from '../hooks';

interface LoadingAnimationProps {
  fullScreen?: boolean;
}

/**
 * System calibration — SVG path-tracing loader.
 * Circle + triangle shapes traced by stroke-dashoffset with a traveling dot.
 * Oxford palette, no rounded corners, institutional motion.
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
      <div className="aethria-loader-group">
        {/* ── Circle ── */}
        <div className={`aethria-loader${reduceMotion ? ' aethria-loader--static' : ''}`}>
          <svg viewBox="0 0 80 80">
            <circle r="32" cy="40" cx="40" />
          </svg>
        </div>

        {/* ── Triangle ── */}
        <div className={`aethria-loader aethria-loader--triangle${reduceMotion ? ' aethria-loader--static' : ''}`}>
          <svg viewBox="0 0 86 80">
            <polygon points="43 8 79 72 7 72" />
          </svg>
        </div>
      </div>

      <div className="mt-phi-5 text-center">
        <p className="type-label-section text-oxford/60">Calibrating workspace</p>
      </div>
    </div>
  );
}
