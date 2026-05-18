import type { LookupResultSnapshotProps, MandateCardProps } from './types';

export const DEMO_MANDATE_DARK: MandateCardProps = {
  variant: 'dark',
  title: 'Deep-Tech Infrastructure',
  tags: ['Series A–B', 'European markets', 'B2B focus'],
  excerpt:
    'Backing infrastructure teams building the plumbing of the next compute cycle — prioritising capital efficiency and defensible wedge.',
  live: true,
};

export const DEMO_MANDATE_PAPER: MandateCardProps = {
  variant: 'paper',
  title: 'Deep-Tech Infrastructure',
  tags: ['B2B Infrastructure', 'Series A–B', 'European Markets'],
  live: true,
};

export const DEMO_LOOKUP_QUERY = 'Meridian Systems';

export const DEMO_LOOKUP_RESULT: LookupResultSnapshotProps = {
  companyName: 'Meridian Systems',
  queryLabel: DEMO_LOOKUP_QUERY,
  metaLine: 'B2B Infrastructure · Series A',
  verdict: 'STRONG.',
  summary:
    'Thesis-aligned · High conviction · Pending unit economics review',
  thesisLine: 'Benchmarked against your active mandate',
  dimensions: [
    { key: 'market', label: 'MKT', score: 9 },
    { key: 'execution', label: 'EXEC', score: 8 },
    { key: 'product', label: 'PROD', score: 8 },
    { key: 'technical', label: 'TECH', score: 9 },
    { key: 'defensibility', label: 'DEF', score: 7 },
  ],
};

/** Marketing homepage — full memo excerpt (DashboardPreview). */
export const DEMO_LOOKUP_MEMO_SAMPLE: LookupResultSnapshotProps = {
  variant: 'memo',
  companyName: 'Meridian Systems',
  metaLine: 'B2B Infrastructure · Series A',
  verdict: 'MONITOR.',
  summary:
    'Clear market timing, credible founding team, and defensible infrastructure play. Conviction is high pending final diligence on unit economics.',
  thesisLine: 'Benchmarked against your active mandate',
  dimensions: [
    { key: 'market', label: 'MARKET', score: 9 },
    { key: 'execution', label: 'EXECUTION', score: 8 },
    { key: 'product', label: 'PRODUCT', score: 8 },
    { key: 'technical', label: 'TECHNICAL', score: 9 },
    { key: 'defensibility', label: 'DEFENSIBILITY', score: 7 },
  ],
};

/** @deprecated Use DEMO_LOOKUP_MEMO_SAMPLE for marketing; snapshot variant for compact previews */
export const DEMO_LOOKUP_RESULT_EXPANDED = DEMO_LOOKUP_MEMO_SAMPLE;
