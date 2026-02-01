import './LoadingAnimation.css';

interface LoadingAnimationProps {
  message?: string;
  fullScreen?: boolean;
}

/**
 * Jelly triangle loading — inspired by Uiverse, adapted for Aethria.
 * Three oxford-blue dots in a triangle; a traveler orbits between them.
 * Gooey filter blends motion. Institutional, restrained.
 */
export default function LoadingAnimation({
  message = 'Loading',
  fullScreen = true,
}: LoadingAnimationProps) {
  const containerClass = fullScreen
    ? 'fixed inset-0 bg-ivory z-[200] flex flex-col items-center justify-center overflow-hidden'
    : 'flex flex-col items-center justify-center py-12 overflow-hidden bg-ivory';

  return (
    <div className={containerClass}>
      {/* SVG filter for jelly/ooze effect */}
      <svg className="absolute w-0 h-0" aria-hidden>
        <defs>
          <filter id="aethria-jelly-ooze" colorInterpolationFilters="sRGB">
            <feGaussianBlur in="SourceGraphic" stdDeviation="6" result="blur" />
            <feColorMatrix
              in="blur"
              mode="matrix"
              values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 18 -8"
              result="thresh"
            />
            <feComposite in="SourceGraphic" in2="thresh" operator="atop" />
          </filter>
        </defs>
      </svg>

      <div className="aethria-jelly-triangle">
        <span className="aethria-jelly-dot" />
        <span className="aethria-jelly-traveler" />
      </div>

      {message && (
        <p className="font-sans text-[10px] uppercase tracking-[0.2em] text-oxford/50 mt-8">
          {message}
        </p>
      )}
    </div>
  );
}
