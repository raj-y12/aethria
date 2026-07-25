/**
 * The front-door wordmark — sign-in and Home, where the mark is a statement
 * rather than chrome.
 *
 * Shared for a mechanical reason, not just tidiness: the sign-in arrival plate
 * morphs its mark into the sign-in frame's via a Framer shared layout. If the
 * two sizes differ, Framer animates the difference as a transform scale, which
 * stretches the glyphs for the whole morph. Keeping every front-door mark on
 * one value keeps that handoff pure translation.
 *
 * Chrome marks are deliberately NOT on this — the spine, mobile header and
 * system bar carry identity at a glance and stay small.
 */
export const FRONT_DOOR_WORDMARK = {
  size: 'text-[clamp(2.6rem,6vw,4rem)]',
  /** Tight leading + tracking the mark is drawn with; loose leading reads as a different mark. */
  face: 'font-wordmark font-medium leading-[0.9] tracking-[-0.02em]',
} as const;
