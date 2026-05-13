import { useEffect } from 'react';
import { animate, motion, useMotionValue, useTransform } from 'framer-motion';

export default function CountUp({
  to,
  delay,
  reduceMotion,
}: {
  to: number;
  delay: number;
  reduceMotion: boolean;
}) {
  const val = useMotionValue(reduceMotion ? to : 0);
  const display = useTransform(val, (v) => Math.round(v).toLocaleString());
  useEffect(() => {
    if (reduceMotion) return;
    const ctrl = animate(val, to, { duration: 0.9, delay, ease: [0.25, 1, 0.5, 1] });
    return ctrl.stop;
  }, [to, delay, reduceMotion, val]);
  return <motion.span>{display}</motion.span>;
}
