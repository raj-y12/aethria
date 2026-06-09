/** Shared Framer Motion easing (marketing site). */
export const SCROLL_EASE: [number, number, number, number] = [0.16, 1, 0.3, 1];

/** Premium spring — buttons, header, layout transitions. */
export const SPRING = { type: 'spring' as const, stiffness: 100, damping: 20 };

export function scrollRevealTransition(duration = 0.55, delay = 0) {
  return {
    duration,
    delay,
    ease: SCROLL_EASE,
  };
}
