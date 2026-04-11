/**
 * Bundles repeated Tailwind class strings so dense UI stays consistent.
 * Prefer `index.css` utilities (`type-label-tab`, `type-meta`, …) where they fit alone.
 */

/** Toolbar / filter row: 11px mono uppercase (tracking matches WorkGrid segments). */
export const UI_DENSE_MONO_UPPER =
  'font-mono text-[11px] font-normal uppercase tracking-[0.1em]' as const;

/** Muted label beside Source, Sort, etc. */
export const UI_FILTER_TOOLBAR_LABEL = `${UI_DENSE_MONO_UPPER} text-oxford/40` as const;

/** Panel chrome (SYSTEM / MEMO actions) — same rhythm as filter labels, fixed tracking. */
export const UI_PANEL_CHROME_LABEL =
  'font-mono text-[11px] font-normal uppercase tracking-[0.1em] text-oxford/40' as const;

/** Segment buttons inside filter row (slightly tighter tracking than kicker labels). */
export const UI_FILTER_SEGMENT_INACTIVE =
  'font-mono text-[11px] font-normal uppercase tracking-[0.08em]' as const;
