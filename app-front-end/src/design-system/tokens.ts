/**
 * Aethria design tokens — aligned with brand_assets and web-front-end.
 *
 * Palette: oxford #002147, paper #F2F0EA, paperBright #faf8f4, inverse on oxford #FFFFFF, charcoal #2f333b.
 * Burgundy #7D2B3A (accent) is escalation-only — see color.accent. Heritage gold #b8976a is decorative only (dividers, chrome) — color.heritageGold.
 * Typography: Libre Baskerville (wordmark / type-hero only). Geist Sans (all UI body, titles, prominent copy). Space Mono (metadata/labels, 0.08–0.14em).
 * Brand scale: section-label 11px/0.12em, tab/meta 10px/0.12–0.14em, intro 13px body 1.6.
 * Frames: 1px rgba(0,33,71,0.06). No rounded corners.
 *
 * Oxford opacity ladder: the only permitted opacities for Oxford-derived text and semantic borders are 100, 80, 60, 40, 25 (percent).
 * Structural frame borders use 0.06 and are the exception.
 */

export const tokens = {
  color: {
    oxford: '#002147',
    paper: '#F2F0EA',
    /** Softer paper lift for gradients and panels (aligned with web-front-end). */
    paperBright: '#faf8f4',
    charcoal: '#2f333b',
    ivory: '#FFFFFF',
    bone: '#f2f4f8',
    mist: '#f2f4f8',
    /** Escalation-only: use only for escalation dots, pulse, escalation counts, critical alerts requiring human attention. */
    accent: '#7D2B3A',
    /** Decorative warm metal — hairlines, non-semantic highlights. Never use for alerts or status. */
    heritageGold: '#b8976a',
    heritageGoldSoft: 'rgba(184, 151, 106, 0.35)',
    /** Warning/validation: subtle warm tint derived from paper; not Tailwind amber. Use for validation errors, non-critical alerts. */
    warningBg: '#F2F0EA',
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
    body: '"Geist Sans", system-ui, -apple-system, sans-serif',
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
   * hero: wordmark only (Libre Baskerville). title: section titles (Geist Sans).
   * body: 14px / 1.6. body-sm: 13px / 1.6.
   * label-section: 11px Space Mono, 0.12em. label-tab: 10px Space Mono, 0.14em. meta: 10px Space Mono, 0.12em.
   */
  type: {
    hero: { size: '28px', lineHeight: 1.4, letterSpacing: '-0.02em', font: 'display' as const },
    title: { size: '24px', lineHeight: 1.5, letterSpacing: '-0.02em', font: 'body' as const },
    body: { size: '14px', lineHeight: 1.6, letterSpacing: '0', font: 'body' as const },
    bodySm: { size: '13px', lineHeight: 1.6, letterSpacing: '0', font: 'body' as const },
    labelSection: { size: '11px', lineHeight: 1.5, letterSpacing: '0.12em', font: 'mono' as const },
    labelTab: { size: '10px', lineHeight: 1.5, letterSpacing: '0.14em', font: 'mono' as const },
    meta: { size: '10px', lineHeight: 1.5, letterSpacing: '0.12em', font: 'mono' as const },
  },
  frameBorder: '1px solid rgba(0, 33, 71, 0.06)',
  motion: {
    ease: [0.16, 1, 0.3, 1] as [number, number, number, number],
    /** micro: tab switch, menu expand/collapse; short/medium/long: content entrance, panels */
    duration: { micro: 0.15, short: 0.4, medium: 0.5, long: 0.6 },
    easeCss: 'cubic-bezier(0.16, 1, 0.3, 1)',
  },
} as const;
