import type { Transition } from 'framer-motion';

/** Single duration when the user prefers reduced motion. */
export const REDUCED_MOTION_TRANSITION: Transition = { duration: 0 };

export function transitionOrReduced(
  reducedMotion: boolean,
  transition: Transition
): Transition {
  return reducedMotion ? REDUCED_MOTION_TRANSITION : transition;
}
