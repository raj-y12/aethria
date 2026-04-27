import { motion } from 'framer-motion';
import { tokens } from '../design-system/tokens';
import { usePrefersReducedMotion } from '../hooks';

interface LoadingAnimationProps {
  fullScreen?: boolean;
}

/** Align with app motion token — smooth orbit, no bounce. */
const EASE = tokens.motion.ease;

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
  const reduceMotion = usePrefersReducedMotion();
  const containerClass = fullScreen
    ? 'fixed inset-0 min-h-[100dvh] bg-paper z-[200] flex flex-col items-center justify-center overflow-hidden'
    : 'flex flex-col items-center justify-center min-h-[200px] py-12 overflow-hidden bg-paper';

  return (
    <div className={containerClass}>
      <div className="relative w-[56px] h-[48px]">
        {VERTICES.map((v, i) =>
          reduceMotion ? (
            <div
              key={i}
              className="absolute top-1/2 left-1/2 rounded-none bg-oxford"
              style={{
                width: POINT_SIZE,
                height: POINT_SIZE,
                marginLeft: -POINT_SIZE / 2 + v.x * 0.35,
                marginTop: -POINT_SIZE / 2 + v.y * 0.35,
                opacity: 0.85,
              }}
            />
          ) : (
            <motion.div
              key={i}
              className="absolute top-1/2 left-1/2 rounded-none bg-oxford"
              style={{
                width: POINT_SIZE,
                height: POINT_SIZE,
                marginLeft: -POINT_SIZE / 2,
                marginTop: -POINT_SIZE / 2,
              }}
              initial={{ x: 0, y: 0, opacity: 0.25, backgroundColor: 'rgba(var(--color-oxford-rgb), 0.25)' }}
              animate={{
                x: [0, v.x, 0],
                y: [0, v.y, 0],
                opacity: [0.25, 1, 0.25],
                backgroundColor: [
                  'rgba(var(--color-oxford-rgb), 0.25)',
                  'rgb(var(--color-oxford-rgb))',
                  'rgba(var(--color-oxford-rgb), 0.25)',
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
          )
        )}
      </div>
    </div>
  );
}
