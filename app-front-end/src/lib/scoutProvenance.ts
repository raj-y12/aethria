/** Backend `field_provenance` keys on scout (enrichment / merge). */
export type ScoutProvenanceField = 'est_tam' | 'funding_stage' | 'references';

const LABELS: Record<string, string> = {
  reviewer_extraction: 'From review extraction',
  reviewer_text_inference: 'Inferred from review text (unverified)',
  gap_retrieval: 'Added from gap retrieval',
  scout: '',
};

export function scoutProvenanceHint(
  provenance: Record<string, string> | undefined,
  field: ScoutProvenanceField
): string | null {
  if (!provenance) return null;
  const raw = provenance[field]?.trim();
  if (!raw || raw === 'scout') return null;
  return LABELS[raw] ?? `Source: ${raw}`;
}
