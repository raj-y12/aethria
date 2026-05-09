const bodyMetrics = 'font-sans text-[13px] leading-[1.5]';

export const railEditorial = {
  /** Primary wordmark — both MainLayout and SettingsPage asides (Libre Baskerville). */
  wordmark:
    'font-wordmark font-normal text-[11px] leading-none tracking-[0.18em] uppercase text-oxford',

  /**
   * Section titles — memo `.memoDocSectionHead` rhythm (tracking, color, mb);
   * font size stays rail scale (11px — former type-meta), not memo --memo-size-label.
   */
  label:
    'mt-0 mr-0 ml-0 mb-[18px] flex items-center gap-3 font-mono text-[11px] font-normal uppercase tracking-[0.12em] text-oxford/60',

  /** Standard rail body text. */
  body: `${bodyMetrics} text-oxford/65`,

  /** Emphasized body — fund names, display names, active values. */
  bodyStrong: `font-sans text-[14px] leading-[1.4] font-medium text-oxford/82`,

  /**
   * Large stat number — WhileYouWereAway-style (sans semibold, −0.03em tracking),
   * scaled down for the narrow rail.
   */
  statValue:
    'font-sans font-semibold tabular-nums leading-none tracking-[-0.03em] text-[clamp(26px,3.5vw,44px)]',

  /** Label beside a stat number. */
  statLabel: 'font-mono text-[10px] leading-none text-oxford/35 tracking-[0.04em]',

  /** Sub-captions, timestamps, link text. */
  meta: 'font-mono text-[10px] leading-[1.4] text-oxford/35 tracking-[0.06em]',

  /** Unstyled size+leading only — apply text color separately. */
  bodyMetrics,
} as const;
