/**
 * Bundles repeated Tailwind class strings so dense UI stays consistent.
 * Prefer `index.css` utilities (`type-label-tab`, `type-meta`, …) where they fit alone.
 */

/** Empty detail pane — ledger awaiting judgment. */
export const UI_DETAIL_EMPTY_HINT =
  'Select a matter to open the investment memo — conviction stays yours.' as const;

/** Judgements panel subtitle tone (optional future use). */
export const UI_JUDGEMENTS_SUBTITLE =
  'Traceable outcomes — partner rules, escalations, resolutions.' as const;

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
