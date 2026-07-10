const bodyMetrics = 'font-sans text-[12px] leading-[1.48]';

export const railEditorial = {
  /** Primary wordmark — paper-surface asides (SettingsPage). Title case in markup. */
  wordmark:
    'font-wordmark font-medium text-[clamp(20px,1.75vw,26px)] leading-tight tracking-normal text-oxford',

  /**
   * Section titles — memo `.memoDocSectionHead` rhythm (tracking, color, mb);
   * font size stays rail scale (11px — former type-meta), not memo --memo-size-label.
   * Bottom margin shrinks on smaller desktop viewports to keep sections compact.
   */
  label:
    'type-label-section mt-0 mr-0 ml-0 mb-[clamp(7px,1.1vw,16px)] flex items-center gap-2',

  /** Standard rail body text. */
  body: `${bodyMetrics} text-oxford/65`,

  /** Emphasized body — fund names, display names, active values. */
  bodyStrong: `font-sans text-[14px] leading-[1.4] font-bold text-oxford/[0.82]`,

  /**
   * Large stat number — Space Mono (tabular), scaled for the narrow rail.
   * Scales down to 20px on tight rail columns (≈1024px viewport) and up to 38px on wide ones.
   */
  statValue:
    'type-data leading-none text-[clamp(20px,2.4vw,38px)]',

  /** Label beside a stat number. */
  statLabel: 'type-label-section leading-none',

  /** Sub-captions, timestamps, link text. */
  meta: 'type-meta',

  /** Small stage/status labels inside rail rows. */
  statusLabel: 'type-status leading-none',

  /** Unstyled size+leading only — apply text color separately. */
  bodyMetrics,
} as const;
