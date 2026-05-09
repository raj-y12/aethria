/**
 * Left-rail editorial stack — matches web-front-end DashboardPreview
 * (border + mono label + 15px sans body).
 */
const bodyMetrics = 'font-sans text-[13px] leading-[1.5]';

export const railEditorial = {
  edge: 'border-l border-solid border-[var(--section-divider)] pl-3 md:pl-4',
  label:
    'mb-1.5 font-mono text-[12px] uppercase tracking-[0.11em] text-[rgba(var(--color-oxford-rgb),0.82)]',
  body: `${bodyMetrics} text-[rgba(var(--color-oxford-rgb),0.78)]`,
  /** Same size/line-height as body; use with `text-oxford` for inputs. */
  bodyMetrics,
} as const;
