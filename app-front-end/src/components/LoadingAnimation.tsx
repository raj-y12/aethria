import { motion } from 'framer-motion';

interface LoadingAnimationProps {
  fullScreen?: boolean;
}

/** Easing: deliberate, no bounce. Instrument-grade. */
const EASE = [0.33, 0, 0.67, 1] as const;

/** Triangle vertices (relative to center). Scaled for larger points. */
const VERTICES = [
  { x: 0, y: -18 },
  { x: -15.6, y: 9 },
  { x: 15.6, y: 9 },
] as const;

const POINT_SIZE = 10;

/**
 * System calibration — continuous sequence, institutional.
 * Three points orbit between center and vertices, oxford blue at peaks.
 * No gooey, no bounce. Calibration, not playfulness.
 */
export default function LoadingAnimation({
  fullScreen = true,
}: LoadingAnimationProps) {
  const containerClass = fullScreen
    ? 'fixed inset-0 bg-paper z-[200] flex flex-col items-center justify-center overflow-hidden'
    : 'flex flex-col items-center justify-center py-12 overflow-hidden bg-paper';

  return (
    <div className={containerClass}>
      <div className="relative w-[56px] h-[48px]">
        {VERTICES.map((v, i) => (
          <motion.div
            key={i}
            className="absolute top-1/2 left-1/2 rounded-full bg-oxford"
            style={{
              width: POINT_SIZE,
              height: POINT_SIZE,
              marginLeft: -POINT_SIZE / 2,
              marginTop: -POINT_SIZE / 2,
            }}
            initial={{ x: 0, y: 0, opacity: 0.25, backgroundColor: 'rgba(0, 33, 71, 0.25)' }}
            animate={{
              x: [0, v.x, 0],
              y: [0, v.y, 0],
              opacity: [0.25, 1, 0.25],
              backgroundColor: [
                'rgba(0, 33, 71, 0.25)',
                'rgb(0, 33, 71)',
                'rgba(0, 33, 71, 0.25)',
              ],
            }}
            transition={{
              duration: 1.2,
              ease: EASE,
              repeat: Infinity,
              repeatDelay: 0.1,
              delay: 0.25 + i * 0.12,
            }}
          />
        ))}
      </div>
    </div>
  );
}
