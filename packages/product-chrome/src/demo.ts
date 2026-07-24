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

export const DEMO_LOOKUP_QUERY = 'European infrastructure co.';

export const DEMO_LOOKUP_RESULT: LookupResultSnapshotProps = {
  companyName: 'European infrastructure co.',
  queryLabel: DEMO_LOOKUP_QUERY,
  metaLine: 'B2B Infrastructure · Series A · London',
  verdict: 'INVEST',
  verdictColor: '#c3d3c9',
  verdictTextColor: '#0a1629',
  summary:
    'Source trail retained · Reviewer disagreement surfaced · Mandate fit recorded',
  thesisLine: 'Investment record prepared for review',
  dimensions: [
    { key: 'market', label: 'MKT', score: 9 },
    { key: 'execution', label: 'EXEC', score: 8 },
    { key: 'product', label: 'PROD', score: 8 },
    { key: 'technical', label: 'TECH', score: 9 },
    { key: 'defensibility', label: 'DEF', score: 7 },
  ],
};

/** Marketing homepage — full memo excerpt variant. */
export const DEMO_LOOKUP_MEMO_SAMPLE: LookupResultSnapshotProps = {
  variant: 'memo',
  companyName: 'European infrastructure co.',
  metaLine: 'B2B Infrastructure · Series A · London',
  verdict: 'MONITOR.',
  summary:
    'Clear market timing, credible founding team, and defensible infrastructure play. Reviewer disagreement remains visible beside the partner recommendation.',
  thesisLine: 'Policy-backed recommendation',
  dimensions: [
    { key: 'market', label: 'MARKET', labelShort: 'MKT', score: 9 },
    { key: 'execution', label: 'EXECUTION', labelShort: 'EXEC', score: 8 },
    { key: 'product', label: 'PRODUCT', labelShort: 'PROD', score: 8 },
    { key: 'technical', label: 'TECHNICAL', labelShort: 'TECH', score: 9 },
    { key: 'defensibility', label: 'DEFENSIBILITY', labelShort: 'DEF', score: 7 },
  ],
};

/** @deprecated Use DEMO_LOOKUP_MEMO_SAMPLE for marketing; snapshot variant for compact previews */
export const DEMO_LOOKUP_RESULT_EXPANDED = DEMO_LOOKUP_MEMO_SAMPLE;
