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
  query: string;
  trailing?: 'run' | 'result';
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
  summary: string;
  dimensions: LookupDimensionScore[];
  thesisLine?: string;
  onOpenMemo?: () => void;
  openMemoLabel?: string;
  /** Compact strip for app rail; memo = marketing sample IC excerpt */
  variant?: LookupResultVariant;
  compact?: boolean;
  intelligenceKicker?: string;
  judgmentLabel?: string;
  dimensionsLabel?: string;
  className?: string;
};
