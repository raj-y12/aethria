const bodyMetrics = 'font-sans text-[13px] leading-[1.5]';

export const railEditorial = {
  /** Primary wordmark — both MainLayout and SettingsPage asides (Libre Baskerville). Title case in markup. */
  wordmark:
    'font-wordmark font-medium text-[clamp(15px,1.35vw,19px)] leading-tight tracking-[0.05em] text-oxford',

  /**
   * Section titles — memo `.memoDocSectionHead` rhythm (tracking, color, mb);
   * font size stays rail scale (11px — former type-meta), not memo --memo-size-label.
   * Bottom margin shrinks on smaller desktop viewports to keep sections compact.
   */
  label:
    'mt-0 mr-0 ml-0 mb-[clamp(8px,1.2vw,18px)] flex items-center gap-3 font-mono text-[11px] font-normal uppercase tracking-[0.12em] text-oxford/60',

  /** Standard rail body text. */
  body: `${bodyMetrics} text-oxford/65`,

  /** Emphasized body — fund names, display names, active values. */
  bodyStrong: `font-sans text-[14px] leading-[1.4] font-medium text-oxford/82`,

  /**
   * Large stat number — JetBrains Mono (tabular), scaled for the narrow rail.
   * Scales down to 20px on tight rail columns (≈1024px viewport) and up to 38px on wide ones.
   */
  statValue:
    'font-mono font-semibold tabular-nums leading-none tracking-[-0.02em] text-[clamp(20px,2.4vw,38px)]',

  /** Label beside a stat number. */
  statLabel: 'font-mono text-[10px] leading-none text-oxford/35 tracking-[0.04em]',

  /** Sub-captions, timestamps, link text. */
  meta: 'font-mono text-[10px] leading-[1.4] text-oxford/35 tracking-[0.06em]',

  /** Small stage/status labels inside rail rows. */
  statusLabel: 'font-mono text-[10px] leading-none uppercase tracking-[0.10em]',

  /** Unstyled size+leading only — apply text color separately. */
  bodyMetrics,
} as const;
