/**
 * Aethria design tokens
 *
 * Locked palette (institutional, restrained):
 * - oxford: Authority accent. Use sparingly (hero emphasis, key headings, focus).
 * - charcoal: Structure & text. Primary body, dividers, metadata.
 * - ivory: Primary canvas. Main background. Flows, no harsh sections.
 * - mist: Secondary planes. Inset areas, subtle depth. Flows with ivory.
 *
 * Typography:
 * - Serif (Libre Baskerville): Aethria name, key headings. font-display.
 * - Sans (Inter): Body, metadata. font-body. Restrained, modern.
 *
 * Layout:
 * - 60% max-width applies ONLY to main content areas (ContentColumn).
 * - Header, footer, hero, background planes: full width.
 * - Prefer borders, spacing, opacity over background fills.
 */

export const tokens = {
  color: {
    oxford: '#002147',
    charcoal: '#2f333b',
    ivory: '#fcfcfc',
    bone: '#f2f4f8',
    mist: '#f2f4f8',
  },
  font: {
    display: '"Libre Baskerville", Georgia, serif',
    body: 'Inter, system-ui, -apple-system, sans-serif',
  },
  layout: {
    contentMaxWidth: '60%',
    contentMaxWidthRem: '38rem',
  },
  /** Enter System page signature — smooth, cinematic. Use across app. */
  motion: {
    ease: [0.16, 1, 0.3, 1] as [number, number, number, number],
    duration: { short: 0.4, medium: 0.5, long: 0.6 },
    easeCss: 'cubic-bezier(0.16, 1, 0.3, 1)',
  },
} as const;
