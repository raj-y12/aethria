export type MandateCardVariant = 'dark' | 'paper';

export type MandateCardProps = {
  variant: MandateCardVariant;
  title: string;
  tags?: string[];
  excerpt?: string;
  live?: boolean;
  /** Tighter padding for app sidebar rail */
  compact?: boolean;
  className?: string;
};

export type LookupCommandBarProps = {
  label?: string;
  query?: string;
  trailing?: 'run' | 'result' | 'close';
  className?: string;
};

export type LookupDimensionScore = {
  key: string;
  label: string;
  score: number | null;
};

export type LookupResultVariant = 'snapshot' | 'memo';

export type LookupResultSnapshotProps = {
  companyName: string;
  queryLabel?: string;
  metaLine?: string;
  verdict: string;
  /** When set, the verdict renders as a filled badge in this colour (matches the queue). */
  verdictColor?: string | null;
  /** Text colour for the filled verdict badge (computed for contrast by the caller). */
  verdictTextColor?: string | null;
  summary: string;
  dimensions: LookupDimensionScore[];
  thesisLine?: string;
  onOpenMemo?: () => void;
  openMemoLabel?: string;
  /** Compact strip for app rail; memo = marketing sample IC excerpt */
  variant?: LookupResultVariant;
  compact?: boolean;
  /** 'lg' enlarges the snapshot (company name, summary, dimension scores, padding)
   * while keeping the same tags/labels — used for the dispatch result takeover. */
  size?: 'default' | 'lg';
  intelligenceKicker?: string;
  judgmentLabel?: string;
  dimensionsLabel?: string;
  className?: string;
};
