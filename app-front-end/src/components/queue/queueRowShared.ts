import type { Startup } from '../../types/startup';
import type { ReviewerQualityBand } from '../../design-system/semantics';
import type { DecisionBadgeVariant } from '../../lib/decisionBadgeVariant';
import type { QueueAttentionDriver, QueueRowContext } from '../../lib/queueAttentionDriver';

export interface DocketRowModel {
  startup: Startup;
  displayIndex: string;
  sourceBadge: 'LOOKUP' | 'SCOUT';
  reviewBand: ReviewerQualityBand | null;
  decisionVariant: DecisionBadgeVariant;
  queueContext: QueueRowContext;
  attentionDriver: QueueAttentionDriver;
  oneLiner: string | null;
  sectorStage: string;
  sortKeyValue: string;
  unresolvedAt: string | null;
  firstSeenAt: string;
  hasHighAdverse: boolean;
  isNewToUser: boolean;
}

const RESOLUTION_BADGE_LABELS: Record<string, string> = {
  PARTIAL: 'Partial evidence',
  LOW_CONFIDENCE: 'Low confidence',
  NEEDS_REVIEW: 'Needs review',
};

/** Company Resolver badge for lookup rows: weak identity evidence is flagged in the
 * queue (instead of the row silently missing). Null when FOUND or not a lookup. */
export function resolutionBadgeLabel(startup: Startup): string | null {
  const status = (startup.scout.resolution_status ?? '').toString().toUpperCase();
  return RESOLUTION_BADGE_LABELS[status] ?? null;
}

export function formatRowDate(value: string): string {
  if (!value) return '';
  return new Date(value).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }).toUpperCase();
}

export function formatUnresolvedAgeDays(value: string): string {
  const time = new Date(value).getTime();
  if (!Number.isFinite(time)) return '';
  const days = Math.max(0, Math.floor((Date.now() - time) / (24 * 60 * 60 * 1000)));
  return `${days}d`;
}

export function buildRowAriaLabel(model: DocketRowModel, isSelected: boolean): string {
  const { startup, attentionDriver, queueContext } = model;
  const rec = queueContext.startup.partner?.recommendation ?? '';
  const score = queueContext.configuredScore;
  const parts = [
    startup.scout.name,
    startup.scout.location?.trim(),
    model.sectorStage || 'Unknown sector',
    attentionDriver.detail ?? attentionDriver.label,
    Number.isFinite(score) && score > 0 ? `Score ${Math.round(score)}` : '',
    rec ? `Recommendation ${rec}` : '',
    isSelected ? 'Selected case' : '',
    'Press Enter to open memo',
  ].filter(Boolean);
  return parts.join('. ');
}
