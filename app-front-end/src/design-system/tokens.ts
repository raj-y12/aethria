/**
 * Aethria design tokens — aligned with brand_assets and web-front-end.
 *
 * Palette: oxford #002147, paper #F2F0EA (warm canvas), ivory #fcfcfc, charcoal #2f333b.
 * Burgundy #7D2B3A (accent) is reserved exclusively for escalation/urgency — see color.accent.
 * Typography: Libre Baskerville (wordmark/hero only — use sparingly), Inter (body, headings, names), Space Mono (metadata/labels).
 * Brand scale: section-label 11px/0.16em, metadata-label 10px/0.22em, intro 13px/0.08em.
 * Frames: 1px rgba(0,33,71,0.06). No rounded corners.
 *
 * Oxford opacity ladder: the only permitted opacities for Oxford-derived text and semantic borders are 100, 80, 60, 40, 25 (percent).
 * Structural frame borders use 0.06 and are the exception.
 */

export const tokens = {
  color: {
    oxford: '#002147',
    paper: '#F2F0EA',
    charcoal: '#2f333b',
    ivory: '#fcfcfc',
    bone: '#f2f4f8',
    mist: '#f2f4f8',
    /** Escalation-only: use only for escalation dots, pulse, escalation counts, critical alerts requiring human attention. */
    accent: '#7D2B3A',
    /** Warning/validation: subtle warm tint derived from paper; not Tailwind amber. Use for validation errors, non-critical alerts. */
    warningBg: '#F5F0E8',
    warningBorder: 'rgba(0, 33, 71, 0.25)',
  },
  /** Oxford opacity ladder: 100, 80, 60, 40, 25. Use these for all muted Oxford text and semantic borders. */
  oxfordOpacity: {
    100: 1,
    80: 0.8,
    60: 0.6,
    40: 0.4,
    25: 0.25,
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
  /**
   * Canonical type scale. Only these levels are permitted. No arbitrary font sizes outside this scale.
   * hero: wordmark/display only (Libre Baskerville). title: section titles (Inter).
   * body: 14px reading. body-sm: 13px — minimum for explanatory text.
   * label-section: panel/section headings, 11px Space Mono 0.16em. label-tab: tabs/chips/badges, 10px Space Mono 0.18em.
   * meta: timestamps, footnotes, 10px Space Mono 0.22em.
   */
  type: {
    hero: { size: '28px', lineHeight: 1, letterSpacing: '-0.02em', font: 'display' as const },
    title: { size: '24px', lineHeight: 1.2, letterSpacing: '-0.02em', font: 'body' as const },
    body: { size: '14px', lineHeight: 1.6, letterSpacing: '0', font: 'body' as const },
    bodySm: { size: '13px', lineHeight: 1.5, letterSpacing: '0', font: 'body' as const },
    labelSection: { size: '11px', lineHeight: 1.2, letterSpacing: '0.16em', font: 'mono' as const },
    labelTab: { size: '10px', lineHeight: 1.2, letterSpacing: '0.18em', font: 'mono' as const },
    meta: { size: '10px', lineHeight: 1.2, letterSpacing: '0.22em', font: 'mono' as const },
  },
  frameBorder: '1px solid rgba(0, 33, 71, 0.06)',
  motion: {
    ease: [0.16, 1, 0.3, 1] as [number, number, number, number],
    /** micro: tab switch, menu expand/collapse; short/medium/long: content entrance, panels */
    duration: { micro: 0.15, short: 0.4, medium: 0.5, long: 0.6 },
    easeCss: 'cubic-bezier(0.16, 1, 0.3, 1)',
  },
} as const;
