/**
 * Secondary hierarchy density — ~8–12% compression for 13" / constrained viewports.
 * Primary scale (hero, title, body 14px, display, selected queue title) stays unchanged.
 *
 * CSS: index.css `:root` + `.memoPanel` overrides in InvestmentMemoContent.css
 * Tailwind: `phi-*` spacing reads `var(--space-*)` from index.css
 */

/** Type scale multiplier applied to secondary utilities only (body-sm, data, memo secondary). */
export const SECONDARY_TYPE_SCALE = 0.92 as const;

/** Spacing multiplier for laptop band (1024–1512px); primary gaps use full scale above that. */
export const LAPTOP_SPACE_SCALE = 0.9 as const;

/** Queue row vertical padding (px) — a compressed docket; selection reads
 *  through ink and the left bar, not expansion. */
export const queueRowPadding = {
  ambient: 10,
  ambientAlt: 11,
  interrupt: 16,
  selected: 14,
} as const;

/**
 * Workspace column grid — 22% / 38% / 40% (sidebar / queue / memo) at lg+.
 */
export const workspaceColumnTargets = {
  sidebar: 0.22,
  queue: 0.38,
  memo: 0.4,
} as const;

/** Editorial measure for embedded memo prose (rem). */
export const MEMO_EDITORIAL_MEASURE_REM = 40;
