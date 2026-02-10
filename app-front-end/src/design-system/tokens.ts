/**
 * Aethria design tokens — aligned with brand_assets and web-front-end.
 *
 * Palette: oxford #002147, paper #F2F0EA (warm canvas), ivory #fcfcfc, charcoal #2f333b.
 * Typography: Libre Baskerville (wordmark/hero only — use sparingly), Inter (body, headings, names), Space Mono (metadata/labels).
 * Brand scale: section-label 11px/0.16em, metadata-label 10px/0.22em, intro 13px/0.08em.
 * Frames: 1px rgba(0,33,71,0.06). No rounded corners.
 */

export const tokens = {
  color: {
    oxford: '#002147',
    paper: '#F2F0EA',
    charcoal: '#2f333b',
    ivory: '#fcfcfc',
    bone: '#f2f4f8',
    mist: '#f2f4f8',
  },
  font: {
    display: '"Libre Baskerville", Georgia, serif',
    body: 'Inter, system-ui, -apple-system, sans-serif',
    mono: '"Space Mono", ui-monospace, monospace',
  },
  /** Brand: page max-width 1800px, padding 32px 20px 80px, section gap 16px */
  layout: {
    pageMaxWidth: '1800px',
    pagePaddingX: '20px',
    pagePaddingY: '32px',
    pagePaddingBottom: '80px',
    sectionGap: '16px',
    contentMaxWidthRem: '38rem',
  },
  /** Brand typography */
  type: {
    sectionLabel: '11px',      // letter-spacing 0.16em, uppercase, opacity 0.6
    metadataLabel: '10px',     // letter-spacing 0.22em, uppercase, mono
    intro: '13px',             // letter-spacing 0.08em, uppercase, opacity 0.7
    title: '28px',             // display, letter-spacing -0.02em
  },
  frameBorder: '1px solid rgba(0, 33, 71, 0.06)',
  motion: {
    ease: [0.16, 1, 0.3, 1] as [number, number, number, number],
    duration: { short: 0.4, medium: 0.5, long: 0.6 },
    easeCss: 'cubic-bezier(0.16, 1, 0.3, 1)',
  },
} as const;
