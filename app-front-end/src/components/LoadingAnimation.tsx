import { motion } from 'framer-motion';

interface LoadingAnimationProps {
  message?: string;
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
 * System calibration — finite sequence, institutional.
 * Three points converge from center, align, lock. Oxford blue at completion.
 * No loop, no gooey, no playfulness. Calibration, not animation.
 */
export default function LoadingAnimation({
  message = 'Loading',
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
            initial={{ x: 0, y: 0, opacity: 0.25 }}
            animate={{
              x: v.x,
              y: v.y,
              opacity: 1,
              backgroundColor: 'rgb(0, 33, 71)',
            }}
            transition={{
              x: { delay: 0.4 + i * 0.06, duration: 0.55, ease: EASE },
              y: { delay: 0.4 + i * 0.06, duration: 0.55, ease: EASE },
              opacity: { delay: 0.4 + i * 0.06, duration: 0.55, ease: EASE },
              backgroundColor: { delay: 1.05, duration: 0.2, ease: EASE },
            }}
          />
        ))}
      </div>

      {message && (
        <motion.p
          className="font-mono text-[10px] uppercase text-oxford/60 mt-8"
          style={{ letterSpacing: '0.22em' }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.0, duration: 0.25, ease: EASE }}
        >
          {message}
        </motion.p>
      )}
    </div>
  );
}
