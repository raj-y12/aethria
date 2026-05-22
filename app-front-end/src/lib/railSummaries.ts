function firstNonEmpty(values: string[]): string | null {
  for (const value of values) {
    const trimmed = value.trim();
    if (trimmed) return trimmed;
  }
  return null;
}

export function buildMandateSummaryLine({
  stages,
  geos,
  sectors,
}: {
  stages: string[];
  geos: string[];
  sectors: string[];
}): string {
  const ordered = [
    firstNonEmpty(stages),
    firstNonEmpty(geos),
    firstNonEmpty(sectors),
  ].filter((value): value is string => value !== null);

  return [...new Set(ordered)].join(' · ');
}
