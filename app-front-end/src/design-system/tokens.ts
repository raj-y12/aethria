/**
 * Aethria design tokens — aligned with brand_assets and web-front-end.
 *
 * Palette: oxford #002147, paper #F2F0EA, paperBright #F2F0EA, inverse on oxford #FFFFFF, charcoal #2f333b.
 * Burgundy #7D2B3A (accent) is escalation-only — see color.accent. Heritage gold #b8976a is decorative only (dividers, chrome) — color.heritageGold.
 * Typography: Libre Baskerville (wordmark / type-hero only). Geist Sans (all UI body, titles, prominent copy). Space Mono (metadata/labels, 0.08–0.14em).
 * Brand scale: section-label 11px/0.12em, tab/meta 10px/0.12–0.14em, body 14px/1.618.
 * Frames: 1px rgba(0,33,71,0.06). No rounded corners.
 * Register tint: CSS variable --color-register-tint (see index.css); Tailwind `registerTint` / `bg-registerTint`.
 *
 * Oxford opacity ladder (100 / 80 / 60 / 40 / 25): preferred for **text** and soft UI chrome.
 * Structural frames use Tailwind semantic `hairline` / `hairline-strong` / `field-border` (see tailwind.config.js).
 *
 * Golden ratio system — φ = 1.618034
 * Spacing: Fibonacci sequence 3→5→8→13→21→34→55→89→144 (each step × φ ≈ next).
 * Type: body 14px base; title = 14×φ ≈ 23px; hero = 23×φ ≈ 37px. Body line-height = φ (1.618).
 * Layout columns: sidebar 38.2% (1/φ²) : content 61.8% (1/φ).
 */

/** φ = 1.618034 — the golden ratio */
export const phi = 1.618034;

/**
 * Golden ratio spacing scale — Fibonacci sequence (each value × φ ≈ next).
 * Use these as the canonical spacing units. Tailwind classes: space-phi-1 … space-phi-9.
 * CSS variables: --space-1 … --space-9.
 */
export const phiSpacing = {
  1: '3px',    //   3 — micro gap, icon padding
  2: '5px',    //   5 — tight inline gap
  3: '8px',    //   8 — compact component padding
  4: '13px',   //  13 — element gap, section gap
  5: '21px',   //  21 — card padding, page padding-x
  6: '34px',   //  34 — section padding, page padding-y
  7: '55px',   //  55 — panel gap
  8: '89px',   //  89 — page bottom padding
  9: '144px',  // 144 — major layout gap
} as const;

export const tokens = {
  color: {
    oxford: '#002147',
    paper: '#F2F0EA',
    /** Softer paper lift for gradients and panels (aligned with web-front-end). */
    paperBright: '#F2F0EA',
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
    /** Editorial headings — Cormorant Garamond (matches --font-display and web-front-end). */
    display: '"Cormorant Garamond", Georgia, "Times New Roman", serif',
    /** Wordmark / type-hero only — Libre Baskerville. */
    wordmark: '"Libre Baskerville", Georgia, serif',
    body: '"Instrument Sans", system-ui, -apple-system, sans-serif',
    mono: '"Space Mono", ui-monospace, monospace',
  },
  /**
   * Layout — values snapped to φ-spacing scale (phiSpacing).
   * page padding-x: φ-5 (21px), padding-y: φ-6 (34px), bottom: φ-8 (89px), section gap: φ-4 (13px).
   * Column ratio: sidebar 38.2% (1/φ²) : content 61.8% (1/φ).
   */
  layout: {
    pageMaxWidth: '1800px',
    pagePaddingX: '21px',    // φ-5
    pagePaddingY: '34px',    // φ-6
    pagePaddingBottom: '89px', // φ-8
    sectionGap: '13px',      // φ-4
    contentMaxWidthRem: '38rem',
    /** Golden ratio column split: sidebar 38.2% / content 61.8% */
    columnRatioSidebar: '38.2%',
    columnRatioContent: '61.8%',
  },
  /**
   * Canonical type scale — golden ratio (φ = 1.618) modular scale anchored at 14px body.
   * body 14px → title 14×φ ≈ 23px → hero 23×φ ≈ 37px.
   * Body line-height = φ (1.618). Labels use 1.5 (density constraint).
   * Only these levels are permitted. No arbitrary font sizes outside this scale.
   */
  type: {
    hero: { size: '37px', lineHeight: 1.2, letterSpacing: '-0.02em', font: 'display' as const },
    title: { size: '23px', lineHeight: 1.382, letterSpacing: '-0.02em', font: 'body' as const },
    body: { size: '14px', lineHeight: 1.618, letterSpacing: '0', font: 'body' as const },
    bodySm: { size: '13px', lineHeight: 1.618, letterSpacing: '0', font: 'body' as const },
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
